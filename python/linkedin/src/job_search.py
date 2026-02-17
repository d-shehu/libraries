from dataclasses        import dataclass

# Local packages
from core               import user_module, logs
from my_secrets         import secret
from scraper            import web_scraper
from utilities          import progress_tracker

# This package
from .acquire           import *
from .authentication    import *
from .format            import *
from .persist           import *
from .queries           import *
from .utilities         import *

class JobStats:
    totalJobs: int
    newJobs: int

    totalRecommendations: int
    newRecommendations: int


class JobSearch(user_module.UserModule):
    def __init__(self, 
                 progressTracker = progress_tracker.ProgressTrackerCLI(), 
                 logMgr = logs.ConfigureConsoleOnlyLogging("JobSearchLogger")
                ):
        super().__init__(logMgr)

        self.scraper         = None
        self.authenticator   = None
        self.formatter       = Formatter(self.logger)
        self.progressTracker = progressTracker

        self.reset()

    def __del__(self):
        if self.scraper is not None:
            del self.scraper

    @property
    def stats(self) -> JobStats:
        return self.__stats

    def getScraper(self):
        return self.scraper

    # Useful when you need restart the search to avoid issues with cookies or other session tracking.
    def reset(self):
        if self.scraper is not None:
            del self.scraper
            
        self.scraper        = web_scraper.WebScraper(logMgr = self.logMgr) # Instantiate new scraper object
        self.authenticator  = Authenticator(self.scraper, self.logger) # Since browser is reset we can reset authenticator
        self.__stats        = JobStats()
        
        return (self.scraper is not None)

    def loadFeed(self):
        if self.authenticator is not None and self.authenticator.isAuthenticated():
            if self.scraper is not None:
                self.scraper.loadPage("https://www.linkedin.com/feed/")
            else:
                raise Exception("Scraper is not initialized.")
        else:
            raise Exception("Can't access the feed. Try logging in first.")
        
    def doLogin(self, username: Optional[secret.Secret], password: Optional[secret.Secret]):
        if (self.authenticator is not None 
            and self.scraper is not None 
            and self.scraper.browser is not None
            ):
            # Retry a few times in case of transient connection issue
            for i in range(1,4):
                self.logger.debug(f"Logging attempt: {i}")
                if self.authenticator.login(username, password):
                    break
        else:
            self.logger.error("Unable to load browser or issues with authenticator")

        return self.authenticator is not None and self.authenticator.isAuthenticated()

    def doLogout(self) -> bool:
        success = False

        if self.authenticator is not None:
            success = self.authenticator.logout()
        else:
            self.logger.error("Authenticator object is invalid.")

        return success
    
    def processJobs(self, collector, description, isRecommendation):
        dfProcessedJobs = None
        
        # Instantiate the progress bar
        lsJobs = collector.getJobsList()
        if len(lsJobs) > 0:
            self.progressTracker.set_description(description)
            self.progressTracker.set_range(0, len(lsJobs))
                
            for job in lsJobs:
                try:
                    collector.parseJobDetails(job, isRecommendation)
                except Exception as e:
                    self.logger.exception("Couldn't parse other fields.") 
                self.progressTracker.increment_value(1)
                
            # Convert to table
            dfProcessedJobs = pd.DataFrame.from_dict(lsJobs)
        
        return dfProcessedJobs

    def search(self, listRoles, listLocations, timespan, maxPages):
        queryBuilder = QueryBuilder(self.scraper, self.logger)
        collector = JobCollector(JOBS_MODE_SEARCH, self.scraper, self.logger)
        
        for role in listRoles:
            for location in listLocations:
                # Search jobs
                url = queryBuilder.getQuery(role, location, timespan)
                self.logger.info(f"Searching: {url}")
                collector.fetchAllJobs(url, maxPages)
    
        # Extract job results
        return self.processJobs(collector, "Processing Search Results: ", False)

    # Return dataframe with job search results. After so many pages, relevance declines dramatically.
    def doSearch(self, locations, roles, timespan = "day", maxPages = 10):
        dfCurrJobs = None
        
        if self.authenticator is not None and self.authenticator.isAuthenticated():
            # Reload feed to reset crawler.
            self.loadFeed()
            dfCurrSearchResults = self.search(roles, locations, timespan, maxPages)
            if dfCurrSearchResults is not None:
                self.logger.info("Found {0} jobs from search".format(dfCurrSearchResults.shape[0]))
            else:
                self.logger.error("Search results dataframe object is not initialized.")
    
            # Clean up, format and sort
            dfCurrJobs = self.formatter.formatJobRecords(dfCurrSearchResults)
        else:
            self.logger.error("Unable to search as user is not authenticated.")

        return dfCurrJobs

    def persistResults(self, gsheetSecret: secret.Secret, spreadsheetURL, sheetLabel, dfJobs) -> UpdateResults:
        serializer = Serializer(gsheetSecret, spreadsheetURL, sheetLabel, self.logger)
        return serializer.updateWorksheet(dfJobs)

    def getRecommendations(self, maxPages):
        collector = JobCollector(JOBS_MODE_RECOMMENDATIONS, self.scraper, self.logger)

        #TODO: add a time filter so we don't get really old postings
        url = "https://www.linkedin.com/jobs/collections/recommended"
        listJobs = collector.fetchAllJobs(url, maxPages)
        
        return self.processJobs(collector, "Processing Recommendations: ", True)
    
    # Quality of recommendations drops off dramatically, more so than
    # search results. Limit search to 1-5 pages at most.
    def doRecommendations(self, maxPages = 5):    
        dfRecommendations = None
        
        if self.authenticator is not None and self.authenticator.isAuthenticated():
            dfRecommendations = self.getRecommendations(maxPages)
            if dfRecommendations is not None:
                self.logger.info("Found {0} recommended jobs".format(dfRecommendations.shape[0]))
    
                # Clean up, format and sort
                dfRecommendedJobs = self.formatter.formatJobRecords(dfRecommendations)
            else:
                self.logger.info("No recommendations to process.")
        else:
            self.logger.error("Unable to search as user is not authenticated.")

        return dfRecommendedJobs