from fake_useragent import UserAgent

from IPython.display import Image

from selenium import webdriver
from selenium.webdriver import FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from selenium.common.exceptions import NoSuchElementException

from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver import ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromiumService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType

import sys
import time

# User module and logging
from core import user_module, logs

# Aliases
LogLine = logs.LogLine

# Constants
USE_DEFINED_TIMEOUT   = -1     # Users can override timeout for specific functions or use the one already defined.
DEFAULT_TIMEOUT_SECS  = 5     # How long to wait before erroring out. 
DEFAULT_SLEEP_SECS    = .250  # Balance between waiting too long to see if element has reloaded and thrashing CPU.

class WebScraper(user_module.UserModule):    
    def __init__(self, width = 1920, height = 1080, 
                 timeout = DEFAULT_TIMEOUT_SECS, 
                 sleep = DEFAULT_SLEEP_SECS, 
                 logMgr = logs.ConfigureConsoleOnlyLogging("WebScraperLogger")):
        super().__init__(logMgr)
        
        # Firefox seems to work better so defaulting to it.
        self.width           = width
        self.height          = height
        self.browser         = self.__getFirefoxBrowser(width, height)
        self.original_window = self.browser.current_window_handle
        self.timeout         = timeout
        self.sleep           = sleep

    def __del__(self):
        if self.browser is not None:
            self.logger.debug("Closing old selenium browser instance")
            self.browser.quit()
        else:
            self.logger.warning("Nothing to cleanup as browser not initialized!")

    def hasBrowser(self):
        return self.browser is not None
        
    def setTimeout(self, timeout):
        self.timeout = timeout

    def __getTimeout(self, timeout):
        if timeout == USE_DEFINED_TIMEOUT:
            return self.timeout
        else:
            return timeout

    # Function to construct browser object
    def __getFirefoxBrowser(self, width, height):
        browser = None
        try:
            self.logger.debug("Initializing Firefox driver...")
            ua = UserAgent(browsers=['Firefox'])
            user_agent = ua.random # Randomize user agent to avoid getting locked out
            self.logger.debug(LogLine("Firefox user agent: ", user_agent))
        
            opts = FirefoxOptions()
            opts.add_argument('--headless')
            opts.add_argument(f'--width={width}')
            opts.add_argument(f'--height={height}')
            opts.add_argument(f'user-agent={user_agent}')
            browser = webdriver.Firefox(options=opts)
            browser.maximize_window()
        except Exception as e:
            self.logger.exception("Unable to load browser service.")
            
        return browser

    # TODO: fix width and height parameter
    def __getChromeBrowser(self, width, height):
        ua = UserAgent(browsers = ['chrome'])
        userAgent = ua.random
        self.logger.debug(LogLine("Chrome user agent: " + userAgent))
        agentOverride = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.53 Safari/537.36'
        
        service=ChromiumService(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
        options = ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument(f'user-agent={userAgent}')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        browser = webdriver.Chrome(service=service,options=options)
        browser.maximize_window()
        browser.execute_cdp_cmd('Network.setUserAgentOverride', 
                                {"userAgent": agentOverride})
        browser.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return browser

    def loadPage(self, url):
        isLoaded = False
        
        try:
            if self.browser is not None:
                self.browser.get(url)
                isLoaded = True
            else:
                self.logger.error("Browser service is not initialized")
        except Exception as e:
            self.logger.exception(f"Unexpected exception while loading: {url}")

        return isLoaded

    def refreshPage(self):
        self.browser.refresh()

    def getCurrentPage(self):
        url = ""
        
        try:
            if self.browser is not None:
                url = self.browser.current_url
        except Exception as e:
            self.logger.exception("Unable to get current page url.")
            
        return url

    def findPopups(self, timeout = USE_DEFINED_TIMEOUT, numPopups = 1):
        listPopups = []
        try:
            timeout = self.__getTimeout(timeout)
            # Wait for one or more popups
            WebDriverWait(self.browser, timeout).until(EC.number_of_windows_to_be(numPopups+1))

            for window_handle in self.browser.window_handles:
                if window_handle != self.original_window:
                    listPopups.append(window_handle)
        except Exception as e:
            self.logger.exception("Unable to scan for popups.")

        return listPopups
            
        
    # Assume there are only 2 windows, main and new one
    def waitForPageURL(self, timeout = USE_DEFINED_TIMEOUT, closeNew=True, switchToOriginal=True):
        urlNew = ""
        
        # Assume new tab or window has been loaded
        try:
            timeout = self.__getTimeout(timeout)
            
            start = time.time()
            # Wait for the new tab to open. There should only be 2.
            WebDriverWait(self.browser, timeout).until(EC.number_of_windows_to_be(2))
    
            # Loop through until we find the new tab handle or time out
            while (time.time() - start) < timeout:
                for window_handle in self.browser.window_handles:
                    if window_handle != self.original_window:
                        self.browser.switch_to.window(window_handle)
                        urlNew=self.getCurrentPage()
                        if urlNew != "" and urlNew != "about:blank":
                            break # Found url?
                            
                # Wait a bit more for new tab to load
                if urlNew != "" and urlNew != "about:blank":
                    time.sleep(self.sleep)
        except Exception as e:
            self.logger.exception("Unexpected exception while waiting for page to load.")

        # Close the newly opened tab or window?
        if closeNew:
            for window_handle in self.browser.window_handles:
                if window_handle != self.original_window:
                    self.browser.switch_to.window(window_handle)
                    self.browser.close()

        # Switch back to the original
        if switchToOriginal:
            self.browser.switch_to.window(self.original_window)

        # If blank assume page couldn't load
        if urlNew == "about:blank":
            self.logger.warning("New page loaded was blank.")
            urlNew = ""

        return urlNew
        
    def waitForURLToChange(self, url, timeout=USE_DEFINED_TIMEOUT, suppressError = False):
        success = False
        
        try:
            timeout = self.__getTimeout(timeout)
            
            WebDriverWait(self.browser, timeout).until(EC.url_changes(url))
            success = True
        except Exception as e:
            if not suppressError:
                self.logger.exception("Timed out while waiting for page to load new url.")

        return success
            
        
    def waitForElementToLoadByXPath(self, elem, timeout=USE_DEFINED_TIMEOUT, suppressError=False):
        return self.waitForElementToLoad(elem, By.XPATH, timeout, suppressError)

    def waitForElementToLoadByID(self, elem, timeout=USE_DEFINED_TIMEOUT, suppressError=False):
        return self.waitForElementToLoad(elem, By.ID, timeout, suppressError)
        
    def waitForElementToLoad(self, elem, byType=By.ID, timeout=USE_DEFINED_TIMEOUT, suppressError=False):
        isLoaded = False

        timeout = self.__getTimeout(timeout)
        if self.getElement(elem, byType, timeout, suppressError) is not None:
            isLoaded = True
            
        return isLoaded

    def getElementByXPath(self, elem, timeout=USE_DEFINED_TIMEOUT, suppressError=False):
        return self.getElement(elem, By.XPATH, timeout, suppressError)
        
    def getElement(self, elem, byType=By.ID, timeout=USE_DEFINED_TIMEOUT, suppressError=False):
        matchingElement = None
        
        if self.browser is not None:
            timeout = self.__getTimeout(timeout)
            # TODO: timer resolution may not be super accurate.
            elapsedTime = 0
            startTime = time.time()
            while matchingElement is None and (elapsedTime < timeout):
                try:
                    matchingElement = self.browser.find_element(byType, elem)
                except NoSuchElementException: # still loading?
                    time.sleep(self.sleep)
                except Exception as e: # other exception?
                    if not suppressError:
                        self.logger.error(LogLine(f"Unexpected exception while getting: {elem}: ", e))
                elapsedTime = time.time() - startTime
                
            if matchingElement is None and elapsedTime >= timeout:
                if not suppressError:
                    self.logger.error(LogLine(f"Timed out waiting for {elem} to load. Elapsed time: ", elapsedTime))
        else:
            if not supressError:
                self.logger.error("Browser service is not initialized")

        return matchingElement

    def getElementFromElementByXPath(self, parent, elem, timeout=USE_DEFINED_TIMEOUT, suppressError=False):
        return self.getElementFromElement(parent, elem, By.XPATH, timeout, suppressError)
        
    def getElementFromElement(self, parent, elem, byType=By.ID, timeout=USE_DEFINED_TIMEOUT, suppressError=False):
        matchingElement = None

        if self.browser is not None:
            timeout = self.__getTimeout(timeout)
            # TODO: timer resolution may not be super accurate.
            elapsedTime = 0
            startTime = time.time()
            
            while matchingElement is None and (elapsedTime < timeout):
                try:
                    matchingElement = parent.find_element(byType, elem)
                except NoSuchElementException: # still loading?
                    time.sleep(self.sleep)
                except Exception as e: # other exception?
                    if not suppressError:
                        self.logger.error(LogLine(f"Unexpected exception while getting {elem}: ", e))
                        
                elapsedTime = time.time() - startTime

            if matchingElement is None and elapsedTime >= timeout:
                if not suppressError:
                    self.logger.error(LogLine(f"Timed out waiting for {elem} to load. Elapsed time: ", elapsedTime))
        else:
            if not supressError:
                self.logger.error("Browser service is not initialized")

        return matchingElement
            

    def getElementsByXPath(self, elem, timeout=USE_DEFINED_TIMEOUT, suppressError=False):
        return self.getElements(elem, By.XPATH, timeout, suppressError)
        
    def getElements(self, elem, byType=By.ID, timeout=USE_DEFINED_TIMEOUT, suppressError=False):
        matchingElements = None

        if self.browser is not None:
            timeout = self.__getTimeout(timeout)
            # TODO: timer resolution may not be super accurate.
            elapsedTime = 0
            keepSearching = True
            matchCount = 0
            startTime = time.time()
            while keepSearching and (elapsedTime < timeout):
                try:
                    WebDriverWait(self.browser, timeout).until(EC.visibility_of_all_elements_located((byType, elem)))
                    matchingElements = self.browser.find_elements(byType, elem)
                except Exception as e:
                    if not suppressError:
                        self.logger.error(LogLine(f"Unexpected exception while getting {elem}: ", e))
                    break

                # Give more time for elements to load
                if (matchingElements is None or len(matchingElements) == 0):
                    time.sleep(self.sleep)
                else:
                    # Found more then iterate again
                    newCount = len(matchingElements)
                    keepSearching = newCount > matchCount
                    matchCount = newCount
                    if keepSearching:
                        time.sleep(self.sleep)

                    
                elapsedTime = time.time() - startTime
                
            if matchingElements is None and elapsedTime >= timeout:
                if not suppressError:
                    self.logger.error(LogLine(f"Timed out waiting for {elem} to load. Elapsed time: ", elapsedTime))
        else:
            if not supressError:
                self.logger.error("Browser service is not initialized")

        return matchingElements

    # Scroll over div parent control to get all the items in the list. Useful if the view
    # does not show all child elements and so elements are not loaded.
    # Rather than returning the elements, invoke a user defined functor which should avoid 
    # issues with DOM getting stale. The functor receives an element.
    def doActionOnElementsInScrollableDivByXPath(self, xpathScrollable, functor, timeout=USE_DEFINED_TIMEOUT, suppressError=False):
        # Assume the specified parent element is scrollable
        # Fetch 1st set of visible elements
        timeout = self.__getTimeout(timeout)
        
        matchingElements = self.getElementsByXPath(xpathScrollable, timeout, suppressError)

        currIndex = 0
        hasMore = True
        while matchingElements is not None and hasMore:
            matchCount = len(matchingElements)
            # Process any new elements that became visible. Presumably these elements
            # the only one guaranteed to not be stale.
            for i in range(currIndex, matchCount):
                functor(matchingElements[i])
            currIndex = matchCount
                
            if matchCount > 0:
                # Scroll last element into view. Assume this expands the list to include everything
                # before plus new elements previously hidden.
                lastElement = matchingElements[-1]
                self.executeScriptOnElement(lastElement, "arguments[0].scrollIntoView();", timeout)
                
                # Get potentailly new elements
                matchingElements = self.getElementsByXPath(xpathScrollable, timeout, suppressError)
            else:
                self.logger.error("Matched 0 scrollable div elements.")
                break

            # If scrolling reveals more elements keep iterating
            hasMore = len(matchingElements) > matchCount

        # Processed at least one element. No way to know if all elements loaded?
        return (currIndex > 0)

    def setElementAttributeByXPath(self, elem, attribute, value, timeout=USE_DEFINED_TIMEOUT):
        return self.setElementAttribute(elem, attribute, value, By.XPATH, timeout)
        
    def setElementAttribute(self, elem, attribute, value, byType=By.ID, timeout=USE_DEFINED_TIMEOUT):
        result = False

        try:
            timeout = self.__getTimeout(timeout)
            
            if self.browser is not None:
                match = self.getElement(elem, byType)
                setAttrScript = f"arguments[0].setAttribute('{attribute}', '{value}')"
                self.executeScriptOnElement(elem, "", timeout)
                result=True
            else:
                self.logger.error("Browser service is not initialized")
        except:
            self.logger.error(f"Unable to access {elem}. Can't find the field by {byType}.")

        return result
    
    def setElementTextByXPath(self, elem, text, hitEnter = False):
        return self.setElementText(elem, text, By.XPATH, hitEnter)
        
    def setElementText(self, elem, text, byType=By.ID, hitEnter = False):
        result = False
        
        try:
            if self.browser is not None:
                match = self.getElement(elem, byType)
                match.clear()
                match.send_keys(text)
                if hitEnter:
                    match.send_keys(Keys.RETURN)
                result=True
            else:
                self.logger.error("Browser service is not initialized")
        except:
            self.logger.error(f"Unable to access {elem}. Can't find the field by {byType}.")

        return result

    def clickOnElementByXPath(self, elem, timeout=USE_DEFINED_TIMEOUT):
        return self.clickOnElement(elem, By.XPATH, timeout)
        
    def clickOnElement(self, elem, byType=By.ID, timeout=USE_DEFINED_TIMEOUT):
        result = False
        lastException = None

        if self.browser is not None:
            timeout = self.__getTimeout(timeout)
            # Retry if there is a transient loading issue with DOM
            elapsedTime = 0
            startTime = time.time()
            while not result and elapsedTime < timeout:
                try:
                    # Handle case when button is obscured by popup by calling click on element via js.
                    element = self.getElement(elem, byType)
                    self.browser.execute_script("arguments[0].click();", element)
                    result=True
                # Save last exception in case there is a non transient error
                except Exception as e:
                    lastException = str(e)
                finally:
                    time.sleep(self.sleep) # sleep to give time to load DOM, etc.
                    elapsedTime = time.time() - startTime
                
        if not result:
            self.logger.error(f"Unable to click on element: {elem}")
            if lastException is not None:
                self.logger.error(LogLine(lastException))
            
        return result

    def executeScriptOnElement(self, element, script, timeout = USE_DEFINED_TIMEOUT):
        executed = False
        result = None
        lastException = None
        
        elapsedTime = 0
        startTime = time.time()
        timeout = self.__getTimeout(timeout)
        while not executed and elapsedTime < timeout:
            try:
                result = self.browser.execute_script(script, element)
                executed = True
            except Exception as e:
                lastException = str(e)
            finally:
                time.sleep(self.sleep) # sleep to give time to load DOM, etc.
                elapsedTime = time.time() - startTime

        if not executed:
            self.logger.error(f"Unable to execute {script} on {element}") 
            if lastException is not None:
                self.logger.error(LogLine(lastException))

        return result

    def getBrowserScreenshot(self):
        # Saves screenshot of entire page
        screenshot = self.browser.get_full_page_screenshot_as_png() 
        return Image(screenshot, width=self.width, height=self.height)
    
    def saveBrowserScreenshot(self, path: str):
        self.browser.save_screenshot(path)
