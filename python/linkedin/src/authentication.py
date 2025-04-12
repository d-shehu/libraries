import getpass

class Authenticator:
    def __init__(self, scraper, logger):
        self.authenticated = False
        self.username      = ""
        self.password      = ""
        self.scraper       = scraper
        self.logger        = logger

    def login(self, username, password):
        if not self.authenticated:
            self.username = username
            self.password = password
            self.authenticated = self.__loadLoginPage() and self.__doLogIn()
        else:
            self.logger.warning("Already authenticated!")

        return self.authenticated

    # Mainly for debugging as there is no need to switch credentials as yet.
    def logout(self):
        raise Exception("Authenticator 'logout' function not defined.")

    def isAuthenticated(self):
        return self.authenticated
            
    def __loadLoginPage(self):
        pageLoaded = False
        
        try:
            self.scraper.loadPage("https://www.linkedin.com/login")
            pageLoaded = self.scraper.waitForElementToLoad("username")
        except Exception as e:
            self.logger.exception("Unable to find field 'username' field in login page.")
    
        if not pageLoaded:
            self.logger.error("Couldn't load login page.")
    
        return pageLoaded

    def __doLogIn(self):
        loginStatus = False
        
        #Fill in form and login
        loginButtonPath="//*/form[@class='login__form']/div[@class='login__form_action_container ']/button"
    
        if (self.scraper.setElementText("username", self.username) 
            and self.scraper.setElementText("password", self.password)
           ):
            urlCurrentPage = self.scraper.getCurrentPage()
            if (self.scraper.clickOnElementByXPath(loginButtonPath)
                and self.scraper.waitForURLToChange(urlCurrentPage)
               ):
                # If redirected to the feed then successfully logged in
                if self.scraper.getCurrentPage() == "https://www.linkedin.com/feed/":
                    loginStatus = True
                # Otherwise check email pin
                else:
                    loginStatus = self.__checkEmailPinChallenge()
            
        return loginStatus

    def __checkEmailPinChallenge(self):
        success = False
        
        # If this screen loads otherwise suppress error as the challenge isn't always triggered.
        if self.scraper.waitForElementToLoadByID("email-pin-challenge"):
            self.logger.info("Linkedin requesting email pin.")
            pin = getpass.getpass()
    
            success = (self.scraper.setElementText("input__email_verification_pin", pin)
                                    and self.scraper.clickOnElement("email-pin-submit-button"))
            if not success:
                self.logger.error("Failed to verify with pin.")
        # Otherwise if element doesn't load assume check isn't triggered
        # Could speed this up by checking if feed is loaded for example. 
        # But since log in happens once per session it's not a big performance hit.
        else:
            success = True 
    
        return success