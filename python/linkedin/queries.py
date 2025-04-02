import re
import urllib.parse

from libraries.python.scraper import web_scraper

# Some hard-coded locations in the US useful for testing.
def fnDefinedLocations(city, state):
    geoID = 0
    
    # New York metropolitan area
    if city == "New York" and state == "New York":
        geoID = 90000070
    elif city == "Philadelphia" and state == "Pennsylvania":
        geoID = 104937023
    elif city == "Princeton" and state == "New Jersey":
        geoID = 106031264
    else:
        print("Unknown location: ", geo)

    return geoID
    
def fnGetGeoIDFromLocation(scraper, city, state, country):
    geoID = 0 # Unknown
    searchURL = "https://www.linkedin.com/jobs/search"

    locationStr = f"{city}, {state}, {country}"

    xpathLocationTextbox="//div[contains(@class, 'jobs-search-box__input--location')]/div/div/input[contains(@class, 'basic-input')]"
    xpathButtonSearch="//button[contains(@class, 'jobs-search-box__submit-button')]"
    if scraper.loadPage(searchURL):
        scraper.refreshPage()

        try:
            # Retry a couple of times as the search seems a bit glitchy
            for i in range(1,3):
                # Linkedin URL changes after initial page load by automatically getting first item.
                if scraper.waitForURLToChange(searchURL, web_scraper.USE_DEFINED_TIMEOUT, True):
                    currSearchURL = scraper.getCurrentPage()

                    # Setting the text triggers the search
                    scraper.clickOnElementByXPath(xpathLocationTextbox)
                    scraper.setElementTextByXPath(xpathLocationTextbox, locationStr, True)
                    scraper.clickOnElementByXPath(xpathButtonSearch)
        
                    # Wait for URL to change to reflect the new geoID
                    if scraper.waitForURLToChange(currSearchURL, web_scraper.USE_DEFINED_TIMEOUT, True):
                        urlWithLoc = scraper.getCurrentPage()
                        
                        # Extract the geoID using this expression.
                        regExpr = "\&geoId=(\d+)"
                        geoIDSearch = re.search(regExpr, urlWithLoc, re.IGNORECASE)
                        if geoIDSearch:
                            geoID = int(geoIDSearch.group(1))
                            break
                    
        except Exception as e:
            print(f"Error: unable to extract geoID from {locationStr}")
            print(e)

    if geoID == 0:
        print(f"Error: could not get geoID from {locationStr}")

    return geoID

# Return all fulltime & permanent jobs posted in the last month within X miles of one of 3 known geos.
# Match on WFH, Hybrid or in-office.
def fnGetQuery(scraper, keywords, location, posted = "day"):

    # TODO: make this selectable
    # Hard code full time, permanent jobs
    jobType = "F" # f_JT
    
    # Modality. Work from home, hybrid and in-office.
    modality = "1%2C2%2C3" # f_WT

    # Required
    city = location["city"]
    if city == "Remote":
        geoID = -1
        modality = "2" # modality is remote only
    else:
        state = location["state"]
        
        # Optional - add country since it seems to speed up geocoding
        country = "United States" # Default for linkedin
        if "country" in location:
            country = location["country"]
        radius = 25 # Also the default for Linkedin
        if "radius" in location:
            radius = location["radius"]

    # Derive geoID from URL if possible
    geoID = fnGetGeoIDFromLocation(scraper, city, state, country)
        
    lastPosted=""
    if posted == "month":
        lastPosted = "r2592000"
    elif posted == "week":
        lastPosted = "r604800"
    elif posted == "day":
        lastPosted = "r86400"
    else:
        print("Unknown time period: ", posted)

    queryURL = ""
    if geoID != 0 and posted != "" and keywords != "":
        # Query
        urlBase = "https://www.linkedin.com/jobs/search/"
        # Arguments
        keywordsEncoded = urllib.parse.quote_plus(keywords)
        arguments = "f_JT={0}&f_TPR={1}&f_WT={2}".format(jobType, lastPosted, modality)
        # Radius search in miles
        arguments = arguments + "&distance={0}".format(radius)
        # If remote exclude geoID argument
        if geoID != -1:
            arguments = arguments + "&geoId={0}".format(geoID)
        # Order of arguments seems important
        arguments = arguments+"&keywords={0}&refresh=true".format(keywordsEncoded)

        queryURL = urlBase + "?" + arguments
    else:
        print("One or more arguments were invalid")
    
    return queryURL

        
