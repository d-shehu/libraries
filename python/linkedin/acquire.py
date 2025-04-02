from enum import Enum
from bs4 import BeautifulSoup
import traceback

from libraries.python.scraper import web_scraper
from .utilities import *

# Python sillyness results in enum from imported file not matching
# passed in value from caller in another file even though it's the only enum 
# with that name. Use int literals to workaround this.
JOBS_MODE_SEARCH          = 1
JOBS_MODE_RECOMMENDATIONS = 2

def fnGetLinkFromButton(scraper):
    # Save original URL
    originalURL = scraper.getCurrentPage()
    urlToApply = ""
        
    try:
        # Find apply button. If it doesn't exist assume the job posting has expired.
        pathToApplyButton = "//*/div[contains(@class, 'jobs-apply-button--top-card')]/button"
        
        # Easy Apply? If so retain the URL of the linkedin posting.
        pathToApplyButtonText = pathToApplyButton + "/span"
        
        applyButtonTextElement = scraper.getElementByXPath(pathToApplyButtonText)
        if applyButtonTextElement is not None:
            applyButtonText = applyButtonTextElement.get_attribute('innerText').strip()
        
            #print("Apply button text: ", applyButtonText)
            if applyButtonText == "Easy Apply":
                #print("Found 'Easy Apply' job posting")
                urlToApply = scraper.getCurrentPage()
            elif applyButtonText == "Apply":
                #print("Found 'Apply' job posting")
                clickOK = scraper.clickOnElementByXPath(pathToApplyButton)
                        
                # Wait to see if "Share your profile" pop up shows up with "Continue"
                pathToShareProfileHeader = "//h2[contains(@id, 'jobs-apply-starter')]"
                profileHeader = scraper.getElementByXPath(pathToShareProfileHeader, 2, True)
                if profileHeader is not None:
                    pathToContinueButton = "//button[contains(@class, 'jobs-apply-button')]"
                    scraper.clickOnElementByXPath(pathToContinueButton)
                
                urlToApply = scraper.waitForPageURL()
                if urlToApply == "":
                    print("Error: couldn't get url to apply for job: ", originalURL)    
            else:
                print("Error: unexpected text found or apply button not found")
        else:
            print("Error: apply button not found")
            
    except Exception as e:
        print("Error: couldn't get apply url for job: ", originalURL)
        print("Exception: ", e)
        print(traceback.format_exc())
        
    #print("URL from apply button: ", urlToApply)
    return urlToApply

def fnParseJobDetails(scraper, geolocator, job):
    parseOK = False
    
    url = job['url']
    # Load the job description
    if scraper.loadPage(url):
        # Introduce a retry mechanism to handle transient DOM loading issues
        for i in range(1, 3):
            try:
                #print(f"(Attempt #: {i}) Parsing: {url}")
                # Start with a freshly reloaded page
                scraper.refreshPage()
                
                # Confirm page has loaded by checking for one of the fields.
                titlePath = "//div[contains(@class, 'job-details-jobs-unified-top-card__job-title')]/h1"
                title = scraper.getElementByXPath(titlePath)
                job["title"] = title.text
                #print("Title: ", job["title"])   
    
                # See the full description. Unclear if XPATH is specific enough since there wasn't an obvious class or ID.
                pathToShowMore = "//footer/button[contains(@class, 'jobs-description__footer-button')]"
                # "See more" button may not exist if the description is shorter.
                if scraper.waitForElementToLoadByXPath(pathToShowMore, web_scraper.USE_DEFINED_TIMEOUT, True):
                    scraper.clickOnElementByXPath(pathToShowMore)
         
                    # Wait for "See less" to load before assuming the profile has loaded
                    pathToShowLess = "//footer/button[contains(@class, 'jobs-description__footer-button')]/span"
                    scraper.waitForElementToLoadByXPath(pathToShowLess)
    
                # Company name and link to about page
                companyPath = "//div[contains(@class, 'job-details-jobs-unified-top-card__company-name')]/a"
                companyElement = scraper.getElementByXPath(companyPath)
        
                job["company"] = companyElement.text
                job["company_url"] = companyElement.get_attribute("href")
                #print("Company: ", job["company"])
                #print("Company URL: ", job["company_url"])

                # Get link from "Apply" button
                job["apply_url"] = fnGetLinkFromButton(scraper)
                #print("Apply URL: ", job["apply_url"])
    
                # Details include location, date/time posted, and number applied without tags
                lsJobDetails = []
                mainDescription = "//div[@class='job-details-jobs-unified-top-card__primary-description-container']/div/span"
                mainDescriptionElements = scraper.getElementsByXPath(mainDescription)
                if mainDescriptionElements is not None and len(mainDescriptionElements) > 0:
                    for element in mainDescriptionElements:
                        lsJobDetails.append(element.get_attribute("innerText"))

                # Details include Comp range, employment_type, work model
                jobDetails = "//button[@class='job-details-preferences-and-skills']/div/span"
                jobDetailsElements = scraper.getElementsByXPath(jobDetails)
                if jobDetailsElements is not None and len(jobDetailsElements) > 0:
                    for element in jobDetailsElements:
                        lsJobDetails.append(element.get_attribute("innerText"))

                #jsonDetails = fnExtractDetailsFromText(ollamaClient, description + "|" + details)
                #print("JSON: ", jsonDetails)
                # Retain origin details and flatten list to a string with pipe delimiters
                job["details"] = "|".join(lsJobDetails)
                fnParseDetails(geolocator, lsJobDetails, job)
        
                # Full description assuming it's loaded
                pathToDescription = "//article[contains(@class, 'jobs-description__container')]/div[contains(@class, 'jobs-description-content')]/div[contains(@class, 'jobs-box__html-content')]"
                descriptionElement = scraper.getElementByXPath(pathToDescription)
                description = BeautifulSoup(descriptionElement.text, "html.parser").get_text()
                #print("Description: ", description)
                job["description"] = description

                parseOK = True
                break # Stop iterating
    
            except Exception as e:
                print("Error while parsing: ", url)
                print("Exception while parsing: ", e)

    return parseOK

class JobsURLFunctor:
    def __init__(self):  
        self.urlList = []
    
    def __call__(self, element) : 
        self.urlList.append(element.get_attribute("href"))

def fnGetJobs(scraper, url, listJobs, mode = JOBS_MODE_SEARCH):
    # Load url if needed
    if scraper.loadPage(url):
        scraper.refreshPage()

        print("URL: ", url)

        collector = JobsURLFunctor();
        xpathJobCardLink = ""
        
        # Previously, used different classes depending on mode: search or recommendations.
        # By switching to A tag, can use the same class as a selector.
        if mode == JOBS_MODE_SEARCH or mode == JOBS_MODE_RECOMMENDATIONS:
            xpathJobCardLink = "//a[contains(@class, 'job-card-list__title--link')]"
        else:
            print("Error: unknown mode for fnGetJobs")

        if (xpathJobCardLink != ""
            and scraper.doActionOnElementsInScrollableDivByXPath(xpathJobCardLink, collector)
           ):
            # Search through the scrollable list of elements and find the job card for each using this utility function.
            numJobs = len(collector.urlList)
            print(f"Found {numJobs} jobs")
        
            for jobURL in collector.urlList:
                listJobs.append({"url": jobURL})
                    
            if numJobs == 0:
                print(f"Warning: no jobs found on current page: {scraper.browser.current_url}")

    return listJobs

def fnFetchJobs(scraper, url, listJobs = [], mode = JOBS_MODE_SEARCH, maxPages = 10):
    startCount = len(listJobs)
    # Wait for jobs page to begin loading
    xpathJobSearchResultsList = "//div[@class='scaffold-layout__list ']"
    if scraper.loadPage(url) and scraper.waitForElementToLoadByXPath(xpathJobSearchResultsList):
        # Always get the 1st and current pages
        fnGetJobs(scraper, url, listJobs, mode)
        iPage = 1

        # Are there more pages and job listings?
        xpathPaginationButton="//div[contains(@class, 'jobs-search-results-list__pagination')]/ul/li/button"
        paginationButtons = scraper.getElementsByXPath(xpathPaginationButton, web_scraper.USE_DEFINED_TIMEOUT, True)
        if paginationButtons is not None:
            numPages = len(paginationButtons)
            print("Number of pages: ", numPages)
            
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
                    break
                print(f"Page {iPage} of {numPages}")
                try:
                    # Click on next page button and wait for it to load
                    # and then process the page.
                    current_url=scraper.getCurrentPage()
                    button.click()
                    scraper.waitForURLToChange(current_url)
                    fnGetJobs(scraper, scraper.getCurrentPage(), listJobs, mode)

                    # If pagination changes update the list
                    print("Get pagination buttons")
                    paginationButtons = scraper.getElementsByXPath(xpathPaginationButton, web_scraper.USE_DEFINED_TIMEOUT, True)
                    numPages = len(paginationButtons)
                    print("Num pages now: ", numPages)
                except Exception as e:
                    print(f"Error: unable to load page {iPage}")
                    print(e)
        else:
            print("Error: couldn't load job search results list!")

    print("Total number of jobs across all pages: ", len(listJobs) - startCount)
    return listJobs