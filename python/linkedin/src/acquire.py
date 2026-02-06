from enum import Enum
from bs4 import BeautifulSoup

from core import logs
from scraper import web_scraper

from .utilities import *

import re

# Aliases
LogLine = logs.LogLine

# Python sillyness results in enum from imported file not matching
# passed in value from caller in another file even though it's the only enum 
# with that name. Use int literals to workaround this.
JOBS_MODE_SEARCH          = 1
JOBS_MODE_RECOMMENDATIONS = 2

# Some hackary to work around linkedin
JOB_ID_PATTERN = re.compile(r"/jobs/view/(\d+)", re.IGNORECASE)

class JobCollector:
    def __init__(self, searchMode, scraper, logger):
        self.searchMode = searchMode
        self.scraper    = scraper
        self.logger     = logger
        self.lsJobs     = []
        self.utilities  = Utilities(logger)
        
    def getJobsList(self):
        return self.lsJobs
        
    def getLinkFromButton(self):
        # Save original URL
        originalURL = self.scraper.getCurrentPage()
        urlToApply = ""
            
        try:
            # Find apply button. If it doesn't exist assume the job posting has expired.
            pathToApplyButton = "//*/div[contains(@class, 'jobs-apply-button--top-card')]/button"
            
            # Easy Apply? If so retain the URL of the linkedin posting.
            pathToApplyButtonText = pathToApplyButton + "/span"
            
            applyButtonTextElement = self.scraper.getElementByXPath(pathToApplyButtonText)
            if applyButtonTextElement is not None:
                applyButtonText = applyButtonTextElement.get_attribute('innerText').strip()
            
                if applyButtonText == "Easy Apply":
                    urlToApply = self.scraper.getCurrentPage()
                elif applyButtonText == "Apply":
                    clickOK = self.scraper.clickOnElementByXPath(pathToApplyButton)
                            
                    # Wait to see if "Share your profile" pop up shows up with "Continue"
                    pathToShareProfileHeader = "//h2[contains(@id, 'jobs-apply-starter')]"
                    profileHeader = self.scraper.getElementByXPath(pathToShareProfileHeader, 2, True)
                    if profileHeader is not None:
                        pathToContinueButton = "//button[contains(@class, 'jobs-apply-button')]"
                        self.scraper.clickOnElementByXPath(pathToContinueButton)
                    
                    urlToApply = self.scraper.waitForPageURL()
                    if urlToApply == "":
                        self.logger.error(f"Couldn't get url to apply for job: {originalURL}")    
                else:
                    self.logger.error("Unexpected text found or apply button not found.")
            else:
                self.logger.error("Apply button not found.")
                
        except Exception as e:
            self.logger.exception(f"Couldn't get apply url for job: {originalURL}")
            
        return urlToApply

    def parseJobDetails(self, job, isRecommendation):
        parseOK = False
        
        url = job['url']

        # Extract the job id
        # Note: a little switch-a-roo to workaround obfuscation of tags
        jobIDMatch = JOB_ID_PATTERN.search(url)
        if jobIDMatch:
            jobID=int(jobIDMatch.group(1))
            url=f"https://www.linkedin.com/jobs/collections/recommended?currentJobId={jobID}"

        # Load the job description
        if self.scraper.loadPage(url):
            # Introduce a retry mechanism to handle transient DOM loading issues
            for i in range(1, 3):
                try:
                    # Start with a freshly reloaded page
                    self.scraper.refreshPage()
                    
                    # Confirm page has loaded by checking for one of the fields.
                    # Using "reconnections" logic path to work around obfuscation. See above.
                    titlePath = "//div[contains(@class, 'job-details-jobs-unified-top-card__job-title')]/h1/a"
                    title = self.scraper.getElementByXPath(titlePath)
                    job["title"] = title.text
                 
                    # See the full description. Unclear if XPATH is specific enough since there wasn't an obvious class or ID.
                    pathToShowMore = "//footer/button[contains(@class, 'jobs-description__footer-button')]"
                    # "See more" button may not exist if the description is shorter.
                    if self.scraper.waitForElementToLoadByXPath(pathToShowMore, web_scraper.USE_DEFINED_TIMEOUT, True):
                        self.scraper.clickOnElementByXPath(pathToShowMore)
             
                        # Wait for "See less" to load before assuming the profile has loaded
                        pathToShowLess = "//footer/button[contains(@class, 'jobs-description__footer-button')]/span"
                        self.scraper.waitForElementToLoadByXPath(pathToShowLess)
        
                    # Company name and link to about page
                    companyPath = "//div[contains(@class, 'job-details-jobs-unified-top-card__company-name')]/a"
                    companyElement = self.scraper.getElementByXPath(companyPath)
            
                    job["company"] = companyElement.text
                    job["company_url"] = companyElement.get_attribute("href")
                    
                    # Get link from "Apply" button
                    job["apply_url"] = self.getLinkFromButton()
        
                    # Details include location, date/time posted, and number applied without tags
                    lsJobDetails = []
                    mainDescription = "//div[@class='job-details-jobs-unified-top-card__primary-description-container']/div/span/span"
                    mainDescriptionElements = self.scraper.getElementsByXPath(mainDescription)
                    if mainDescriptionElements is not None and len(mainDescriptionElements) > 0:
                        for element in mainDescriptionElements:
                            lsJobDetails.append(element.get_attribute("innerText"))
    
                    # Details include Comp range, employment_type, work model
                    jobDetails = "//div[@class='job-details-fit-level-preferences']/button/span//strong"
                    jobDetailsElements = self.scraper.getElementsByXPath(jobDetails)
                    if jobDetailsElements is not None and len(jobDetailsElements) > 0:
                        for element in jobDetailsElements:
                            lsJobDetails.append(element.get_attribute("innerText"))
    
                    # Retain origin details and flatten list to a string with pipe delimiters
                    job["details"] = "|".join(lsJobDetails)
                    self.utilities.parseDetails(lsJobDetails, job)
            
                    # Full description assuming it's loaded
                    pathToDescription = "//article[contains(@class, 'jobs-description__container')]/div[contains(@class, 'jobs-description-content')]/div[contains(@class, 'jobs-box__html-content')]"
                    descriptionElement = self.scraper.getElementByXPath(pathToDescription)
                    description = BeautifulSoup(descriptionElement.text, "html.parser").get_text()
                    
                    job["description"] = description
    
                    parseOK = True
                    break # Stop iterating
        
                except Exception as e:
                    self.logger.exception(f"Error while parsing: {url}")
    
        return parseOK

    def getJobs(self, url):
        # Load url if needed
        if self.scraper.loadPage(url):
            self.scraper.refreshPage()
    
            self.logger.info(f"Jobs URL: {url}")
    
            collector = JobsURLFunctor();
            xpathJobCardLink = ""
            
            # Previously, used different classes depending on mode: search or recommendations.
            # By switching to A tag, can use the same class as a selector.
            if self.searchMode == JOBS_MODE_SEARCH or self.searchMode == JOBS_MODE_RECOMMENDATIONS:
                xpathJobCardLink = "//a[contains(@class, 'job-card-list__title--link')]"
            else:
                self.logger.error(f"Unknown search mode {self.searchMode} for getJobs")
    
            if (xpathJobCardLink != ""
                and self.scraper.doActionOnElementsInScrollableDivByXPath(xpathJobCardLink, collector)
               ):
                # Search through the scrollable list of elements and find the job card for each using this utility function.
                numJobs = len(collector.urlList)
                self.logger.info(f"Found {numJobs} jobs")
            
                for jobURL in collector.urlList:
                    self.lsJobs.append({"url": jobURL})
                        
                if numJobs == 0:
                    self.logger.warning(f"No jobs found on current page: {self.scraper.browser.current_url}")
    
    def fetchAllJobs(self, url, maxPages = 10):
        # Keep track of jobs added across pages
        startCount = len(self.lsJobs)
        
        # Wait for jobs page to begin loading
        xpathJobSearchResultsList = "//div[@class='scaffold-layout__list ']"
        if self.scraper.loadPage(url) and self.scraper.waitForElementToLoadByXPath(xpathJobSearchResultsList):
            # Always get the 1st and current pages
            self.getJobs(url)
            iPage = 1
    
            # Are there more pages and job listings?
            xpathPaginationButton="//div[contains(@class, 'jobs-search-results-list__pagination')]/ul/li/button"
            paginationButtons = self.scraper.getElementsByXPath(xpathPaginationButton, web_scraper.USE_DEFINED_TIMEOUT, True)
            if paginationButtons is not None:
                numPages = len(paginationButtons)
                self.logger.debug(f"Number of pages: {numPages}")
                
                # Number of pages could change between iterations. Limit to
                # a reasonable maximum.
                # Note: there is an issue where contents of page could change
                # in between loading of pages affecting previously parsed pages.
                while iPage < min(numPages, maxPages):
                    # Go through the other pages and fetch jobs from each
                    button = paginationButtons[iPage]
                    iPage = iPage + 1
                    # Break if exceeding maxPages
                    if iPage > maxPages:
                        self.logger.info(f"Maximum pages of jobs {maxPages} reached")
                        break
                    self.logger.debug(f"Page {iPage} of {numPages}")
                    
                    try:
                        # Click on next page button and wait for it to load
                        # and then process the page.
                        current_url=self.scraper.getCurrentPage()
                        button.click()
                        self.scraper.waitForURLToChange(current_url)
                        self.getJobs(self.scraper.getCurrentPage())
    
                        # If pagination changes update the list
                        self.logger.debug("Get pagination buttons")
                        paginationButtons = self.scraper.getElementsByXPath(xpathPaginationButton, web_scraper.USE_DEFINED_TIMEOUT, True)
                        numPages = len(paginationButtons)
                        self.logger.debug(f"Num pages now: {numPages}")
                    except Exception as e:
                        self.logger.exception(f"Unable to load page {iPage}")
            else:
                self.logger.error("Couldn't load job search results list!")
    
        self.logger.info(LogLine("Total number of jobs across all pages: ", len(self.lsJobs) - startCount))

class JobsURLFunctor:
    def __init__(self):  
        self.urlList = []
    
    def __call__(self, element) : 
        self.urlList.append(element.get_attribute("href"))