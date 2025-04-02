# 3P Packages
from geopy.geocoders import Nominatim
import pathlib
import os
from random import choice
from string import ascii_uppercase
import subprocess
import sys
import time

# Local Packages
from libraries.python.utilities import common
from libraries.python.scraper import web_scraper

# This package
from .acquire import *
from .authenticate import *
from .format import *
from .persist import *
from .queries import *
from .utilities import *

def fnInstallDependencies():
    # Install packages needed by scraper
    common.fnInstallDependencies()
    scraper.fnInstallDependencies()
    
    # Install my dependencies
    scriptParentDir = pathlib.Path(__file__).parent.resolve()
    subprocess.check_call([sys.executable, "-m", "pip", "install", f"{scriptParentDir}/requirements.txt"])


class JobSearch:
    def __init__(self, progressTracker = common.ProgressTrackerCLI()):
        # To ensure uniqueness for geolocator assign a somewhat name by appending random letters.
        agentName            = "JobSearch_" + ''.join(choice(ascii_uppercase) for i in range(10))
        self.geolocator      = Nominatim(user_agent = agentName)
        self.scraper         = None
        self.progressTracker = progressTracker
        self.reset()

    def __del__(self):
        if self.scraper is not None:
            del self.scraper


    def getScraper(self):
        return self.scraper

    # Useful when you need restart the search to avoid issues with cookies or other session tracking.
    def reset(self):
        if self.scraper is not None:
            del self.scraper
            
        self.scraper       = web_scraper.WebScraper() # Instantiate new scraper object
        self.authenticated = False

        return (self.scraper is not None)

    def loadFeed(self):
        if self.authenticated:
            self.scraper.loadPage("https://www.linkedin.com/feed/")
        else:
            raise Exception("Can't access the feed, log in first.")
        
    def doLogin(self, username, password):
        self.authenticated = False
        
        if self.scraper.browser is not None:
            # Retry a few times in case of transient connection issue
            for i in range(1):
                print("Info: Logging attempt: ", i+1)
                fnLoadLoginPage(self.scraper)
                if fnDoLogIn(self.scraper, username, password):
                    # Check for verification request
                    self.authenticated = fnCheckEmailPinChallenge(self.scraper)
        else:
            print("Error: unable to load browser")

        return self.authenticated

    def processJobs(self, listJobs):
        dfProcessedJobs = None
        
        # Instantiate the progress bar
        if len(listJobs) > 0:
            self.progressTracker.set_range(0, len(listJobs))
                
            for job in listJobs:
                try:
                    fnParseJobDetails(self.scraper, self.geolocator, job)
                except Exception as e:
                    print("Couldn't parse other fields: ", e) 
                self.progressTracker.increment_value(1)
                
            # Convert to table
            dfProcessedJobs = pd.DataFrame.from_dict(listJobs)
        
        return dfProcessedJobs

    def search(self, listRoles, listLocations, timespan):
        listJobs = []
        
        for role in listRoles:
            for location in listLocations:
                # Search jobs
                url = fnGetQuery(self.scraper, role, location, timespan)
                print("Info: Searching: ", url)
                listJobs = fnFetchJobs(self.scraper, url, listJobs)
    
        # Extract job results
        return self.processJobs(listJobs)

    # Return dataframe with job search results
    def doSearch(self, locations, roles, timespan = "day"):
        dfCurrJobs = None
        
        if self.authenticated:
            # Reload feed to reset crawler.
            self.loadFeed()
            dfCurrSearchResults = self.search(roles, locations, timespan)
            print("Info: Found {0} jobs from search".format(dfCurrSearchResults.shape[0]))
    
            # Clean up, format and sort
            dfCurrJobs = fnFormatJobRecords(dfCurrSearchResults)
            dfCurrJobs = dfCurrJobs.fillna("")
        else:
            print("Error: Unable to search as user is not authenticated.")

        return dfCurrJobs

    def persistResults(self, spreadsheetURL, sheetLabel, dfJobs):
        return fnUpdateWorksheet(spreadsheetURL, sheetLabel, dfJobs)

    def getRecommendations(self, numPages):
        listJobs = []

        #TODO: add a time filter so we don't get really old postings
        url = "https://www.linkedin.com/jobs/collections/recommended"
        listJobs = fnFetchJobs(self.scraper, url, listJobs, JOBS_MODE_RECOMMENDATIONS, numPages)
        
        return self.processJobs(listJobs)
    
    # Quality of recommendations drops off dramatically, more so than
    # search results. Limit search to 1-5 pages at most.
    def doRecommendations(self, numPages = 5):    
        dfRecommendations = None
        
        if self.authenticated:
            dfRecommendations = self.getRecommendations(numPages)
            print("Info: Found {0} recommended jobs".format(dfRecommendations.shape[0]))
    
            # Clean up, format and sort
            dfRecommendedJobs = fnFormatJobRecords(dfRecommendations)
            dfRecommendedJobs = dfRecommendedJobs.fillna("")
        else:
            print("Error: Unable to search as user is not authenticated.")

        return dfRecommendedJobs