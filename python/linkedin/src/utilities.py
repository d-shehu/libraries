from datetime import date
from datetime import datetime as dt
from dateutil.relativedelta import relativedelta
from geopy.geocoders import Nominatim
from geopy import distance
import pandas as pd
from random import choice
import re
from string import ascii_uppercase

def GetDateFormatStr():
    return "%m/%d/%Y"

def GetISODateFormatStr():
    return "%Y-%m-%d"

def InvalidDate():
    return dt(year=1,month=1,day=1)

def PrintJobResults(dfSearchResults, columns=["title", "company", "city", "employment_type", "work_model"]):
    with pd.option_context('display.max_colwidth', None):
        display(dfSearchResults[columns])
    
class Utilities:
    def __init__(self, logger):
        self.logger = logger

        # To ensure uniqueness for geolocator assign a somewhat name by appending random letters.
        agentName       = "JobSearch_" + ''.join(choice(ascii_uppercase) for i in range(10))
        self.geolocator = Nominatim(user_agent = agentName)

    def getDateStr(self, d, funFormat = GetDateFormatStr):
        if type(d) == str:
            return d
        elif not pd.isnull(d) and d != InvalidDate():
            return d.strftime(funFormat())
        else:
            self.logger.error("Unable to parse unexpected date format")
            return ""

    def getDateFromStr(self, dtStr, funFormat = GetDateFormatStr):
        ret = InvalidDate()
        
        try:
            if dtStr != "":
                ret =  dt.strptime(dtStr, funFormat())
        except:
            self.logger.exception(f"Unable to parse date: {dtStr}")
            
        return ret

    def parsePosted(self, str, date):
        try:
            numbers = re.findall("\d+", str)
            units = re.findall("(minute|hour|day|week|month)", str)
    
            if len(numbers) == 1 and len(units) == 1:
                number = int(numbers[0])
                if units[0] == "day":
                    date = date - relativedelta(days=number)
                elif units[0] == "week":
                    date = date - relativedelta(weeks=number)
                elif units[0] == "month":
                    date = date - relativedelta(months=number)
                # Nearest day is sufficient. For more precise info look at linkedin's posted date.
                elif units[0] != "minute" and units[0] != "hour":
                    self.logger.error("Unexpected unit: ", units[0])
                    date = None
                    
        except Exception as e:
            self.logger.exception("Unable to parse posted date/time.")
            date = None
            
        dateStr = ""
        if date is not None:
            dateStr = self.getDateStr(date)
            
        return dateStr

    def parseAppliedCount(self, str):
        appliedCount = -1
        
        try:
            numbers = re.findall("\d+", str)
            
            # Match a single number
            if len(numbers) == 1:
                appliedCount = int(numbers[0])
            else:
                self.logger.error("Applied count can't be parsed.")
                
        except Exception as e:
            self.logger.exception("Applied count can't be parsed due to exception.")
    
        return appliedCount

    def parseLocation(self, str, job):
        success = False
    
        # Initialize
        job["location"] = {}
    
        try:
            # Multiple tokens delimited by ',' imply specific location
            if str.find(",") != -1:
                location = self.geolocator.geocode(str)
                if location is not None:
                    address = self.geolocator.reverse(location.raw["lat"] + ", " + location.raw["lon"]).raw["address"]
    
                    # Pick city, municipality and town in that order for the placename
                    placename = ""
                    if "city" in address:
                        placename = address["city"]
                    elif "municipality" in address:
                        placename = address["municipality"]
                    elif "town" in address:
                        placename = address["town"]
                    # If there are multiple tokens in address I'd expect at least
                    # to get a state. For example Texas, United States.
                    elif not "state" in address:
                        raise Exception("Could not find placename or jurisdiction in address.")
    
                    if placename == "":
                        # Postal code, country & lat/lon is useless without a specific placename (city, town)
                        job["location"] = {
                            "placename": "",
                            "county":    "",
                            "state":     address["state"]   if "state"   in address else "",
                            "country":   address["country"] if "country" in address else "",
                            "postcode":  "",
                            "lat":       "",
                            "lat":       ""
                        }
                    else:
                        job["location"] = {
                            "placename": placename,
                            "county":    address["county"]   if "county"   in address else "",
                            "state":     address["state"]    if "state"    in address else "",
                            "country":   address["country"]  if "country"  in address else "",
                            "postcode":  address["postcode"] if "postcode" in address else "",
                            "lat":       location.raw["lat"] if "lat"      in location.raw else "",
                            "lon":       location.raw["lon"] if "lon"      in location.raw else ""
                        }
                    # Able to parse some fields
                    success = True
        except Exception as e:
            self.logger.exception("Exception while trying to parse location.")
                    
        # Probably just the country i.e. remote-only location such as "United States"
        # Some other special cases mat fall into this such as Albany, New York Metropolitan Area.
        if not success:
            self.logger.warning(f"Unable to geocode '{str}'. Falling back to simple tokenization.")
            placename = ""
            state     = ""
            # Fallback to simple logic, split into tokens and assign placename and state to the first 2
            # tokens assuming they exist
            try:
                locTokens = str.split(",")
                if len(locTokens) > 0:
                    placename = locTokens[0]
                if len(locTokens) > 1:
                    state = locTokens[1]
                
                success = True # No other exceptions go ahead and passthrough
            except Exception as e:
                self.logger.exception(f"Unable to apply simple tokenization logic to location: {str}")
    
            # Always init location with expected fields to avoid triggering exception in other parts of code.
            job["location"] = {
                    "placename": placename,
                    "state":     state,
                    "county":    "",
                    "country":   "",
                    "postcode":  "",
                    "lat":       0,
                    "lon":       0
            }
        
        return success
    
    # Details can be location, time posted, applied count, range, workplace type, working model 
    def parseDetails(self, lsDetails, job):
    
        matchLocation = False
    
        # Initialize
        job["location"]        = {}
        job["posted"]          = ""
        job["posted_date"]     = None
        job["applied_count"]   = ""
        job["compensation"]    = ""
        job["work_model"]      = ""
        job["employment_type"] = ""
    
        if len(lsDetails) > 0:
            # Location: To minimize calls to geocoder (rate limiting) assume 1st detail is location.
            # All job posting should have a location
            matchLocation = self.parseLocation(lsDetails[0], job)
            
            # Match most common patterns such as $122 per hour or 125K/yr.
            ratePattern = "\$\s*\d+(\.\d+)*\s*K*(\/\s*(yr|year|hr|hour))"
            compPattern = f"{ratePattern}(\s*-\s*{ratePattern})*"
            
            for i in range(1, len(lsDetails)):
                detail = lsDetails[i]
                # Skip delimiter
                if re.match("^\s*·\s*", detail) is None:    
                    # Date/time posted
                    # Derive the posted date which is a slightly inaccurate process since it doesn't account for processing. 
                    # Linkedin itself isn't very precise (1 day ago, etc.)
                    if re.match("^(Posted|Reposted)?\s*(\d+ (minute|hour|day|week|month)s? ago)", detail):
                        job["posted"]      = detail
                        job["posted_date"] = self.parsePosted(detail, date.today())
                    # Applied count
                    elif (re.match("(Over\s+)*\d+\s+(people|person)\s+(clicked)\s+(apply)", detail) 
                          or re.match("(Over\s+)*\d+\s+(applicants)", detail)
                         ):
                        job["applied_count"] = self.parseAppliedCount(detail)
                    
                    # Salary or salary range
                    elif re.match(compPattern, detail):
                        job["compensation"] = detail
                    # Working model: hybrid, remote, on-site
                    elif re.match("(On-site)|(Remote)|(Hybrid)", detail):
                        job["work_model"] = detail
                    # Employment time: 
                    elif re.match("(Full-time)|(Part-time)|(Contract)|(Temporary)|(Volunteer)|(Internship)|(Other)", detail):
                        job["employment_type"] = detail
                    else:
                        self.logger.warning(f"Unexpected detail found: {detail}")
        else:
            raise Exception("Expected some job details including location")
            
    
        # Less than useful without location and this is a "required field"
        return matchLocation
