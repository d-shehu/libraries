import getpass

from libraries.python.scraper import web_scraper

def fnLoadLoginPage(scraper):
    pageLoaded = False
    
    try:
        scraper.loadPage("https://www.linkedin.com/login")
        pageLoaded = scraper.waitForElementToLoad("username")
    except Exception as e:
        print("Error: unable to find 'username' field in login page: ", e)

    if not pageLoaded:
        print("Error: couldn't load login page")

    return pageLoaded

def fnDoLogIn(scraper, username, password):
    loginStatus = False
    
    #Fill in form and login
    loginButtonPath="//*/form[@class='login__form']/div[@class='login__form_action_container ']/button"

    if (scraper.setElementText("username", username) 
        and scraper.setElementText("password", password)
       ):
        urlCurrentPage = scraper.getCurrentPage()
        if (scraper.clickOnElementByXPath(loginButtonPath)
            and scraper.waitForURLToChange(urlCurrentPage)
            and scraper.getCurrentPage() == "https://www.linkedin.com/feed/"
           ):
            loginStatus = True
        
    return loginStatus

def fnCheckEmailPinChallenge(scraper):
    success = False
    
    # If this screen loads otherwise suppress error as the challenge isn't always triggered.
    if scraper.waitForElementToLoadByID("email-pin-challenge", web_scraper.USE_DEFINED_TIMEOUT, True):
        pin=getpass.getpass()

        success = (scraper.setElementText("input__email_verification_pin", pin)
                                and scraper.clickOnElement("email-pin-submit-button"))
        if not success:
            print("Error: failed to verify with pin")
    # Otherwise if element doesn't load assume check isn't triggered
    # Could speed this up by checking if feed is loaded for example. 
    # But since log in happens once per session it's not a big performance hit.
    else:
        success = True 

    return success