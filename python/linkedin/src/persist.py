import pandas as pd
import gspread
from gspread_formatting import *
from oauth2client.service_account import ServiceAccountCredentials
import os

from .format import *
from .utilities import *

class Serializer:
    def __init__(self, gsheetSecretsFilepath, spreadsheetURL, sheetLabel, logger):
        self.logger        = logger
        self.credentials   = None
        self.gsheetsClient = None
        self.sheet         = None
        self.worksheet     = None
        #self.formatter     = Formatter(self.logger)
        self.utilities     = Utilities(self.logger)

        # Connect to Google Sheets. Assume the secret file is at this location.
        # Also assumes there is a service account associated with secret which 
        # has read/write permission on sheet.
        gsheetSecretsFilepath = os.path.expandvars(gsheetSecretsFilepath)
        self.logger.debug(f"Reading gsheet secrets from: {gsheetSecretsFilepath}")
        self.authorizeGoogleSheets(gsheetSecretsFilepath)
        self.loadWorksheetFromGoogleDrive(spreadsheetURL, sheetLabel)
        
    def authorizeGoogleSheets(self, credentialsFilepath):
        scope = ["https://www.googleapis.com/auth/spreadsheets",
                 "https://www.googleapis.com/auth/drive"]
    
        try:
            self.logger.debug(f"Credentials filepath: {credentialsFilepath}")
            self.credentials = ServiceAccountCredentials.from_json_keyfile_name(credentialsFilepath, scope)
            self.gsheetsClient = gspread.authorize(self.credentials)
        except Exception as e:
            self.logger.exception("Unable to get access to Google sheets.")

    def loadWorksheetFromGoogleDrive(self, url, sheetLabel):
        try:
            # Assume the spreadsheet exists and has a tab "Search"
            self.sheet = self.gsheetsClient.open_by_url(url)
            # Read the spreadsheet into a date frame. Assume there is a tab "Search" with all search results.
            self.worksheet = self.sheet.worksheet(sheetLabel)
            
        except Exception as e:
            self.logger.exception(f"Unable to load worksheet {sheetLabel} at {url}")

    def isLoaded(self):
        return (self.gsheetsClient is not None 
                and self.sheet is not None
                and self.worksheet is not None)

    def flagDuplicates(self, df):
        dfUpdated = df
        updatedCount = 0
        
        # Flag duplicate based on columns which uniquely identify a job posting.
        # Logic is slightly modified to account for jobs being reposted periodically
        # So consider any job to be a duplicate if it was posted within 1 month period
        # of the first assuming all matches.
        # Return copy of data frame if modified
        if df.shape[0] > 1:
            idColumns = GetIDColumns()
        
            dfSorted = df.sort_values(by=idColumns)
        
            firstDate = self.utilities.getDateFromStr(dfSorted.loc[0, "posted_date"], GetISODateFormatStr)
        
            for i in range(1, dfSorted.shape[0]):
                prev = dfSorted.iloc[i-1]
                curr = dfSorted.iloc[i]
                
                if DoesIDMatchExcludingDate(prev, curr):
                    # Calculate the number of days elapsed since this was "reposted" potentially.
                    days = (self.utilities.getDateFromStr(curr["posted_date"], GetISODateFormatStr) - firstDate).days
                    if days < 30:
                        # Let's avoid overriding if status was explicitly modified:
                        status = curr["status"]
                        if status != "Apply" and status != "Closed" and status != "Assess" and status != "Discard" and status != "Duplicate":
                            dfSorted.at[i, "status"] = "Duplicate"
                            updatedCount += 1
                    # After 30 days let's assume it's a different job or worth revisiting
                    else:
                        firstDate = self.utilities.getDateFromStr(dfSorted.loc[i, "posted_date"], GetISODateFormatStr)
                # Different job
                else:
                    firstDate = self.utilities.getDateFromStr(dfSorted.loc[i, "posted_date"], GetISODateFormatStr)
                    
            dfUpdated = dfSorted
            
            self.logger.info(f"Duplicates: {updatedCount}")
        else:
            self.logger.warning("Trying to remove duplicates from dataframe with 0 or 1 rows")
            
        return dfUpdated

    

    def loadJobsFromWorksheet(self):
        dfJobsOnFile = None
    
        try:
            # TODO: consider if the list gets too large for in-memory processing
            recordsOnFile = self.worksheet.get_all_records()
            if recordsOnFile != []:
                dfJobsOnFile = pd.DataFrame(recordsOnFile)
            else:
                dfJobsOnFile = pd.DataFrame()
        
            self.logger.info("Records on file: {0}".format(dfJobsOnFile.shape[0]))
        except Exception as e:
            self.logger.exception("Unable to load jobs search results from Google sheets.")
    
        return dfJobsOnFile

    def combineResults(self, dfJobsOnFile, dfCurrJobs):
        dfJoined = None
        if dfJobsOnFile is not None:
            if (dfJobsOnFile.shape[0] > 0 and dfCurrJobs.shape[0] > 0):
                print("Info: Combining records on file with new entries")
                # Combine on file records with new entries. On file take precedence over new if duplicates are found.
                # This resumes only exact duplicates. See below for flagging duplicates posted on different dates.
                dfUnion = pd.concat(objs = [dfJobsOnFile,dfCurrJobs], axis = 0, join = "outer", ignore_index = True, keys = None)
                dfJoined = dfUnion.drop_duplicates(subset=GetIDColumns(), keep='first', inplace=False, ignore_index=True)
                dfJoined = dfJoined.reset_index(drop=True)
            elif dfJobsOnFile.shape[0] > 0:
                # No new jobs
                self.logger.info("No new jobs!")
                dfJoined = dfJobsOnFile
            else:
                self.logger.info("No jobs on file.")
                dfJoined = dfCurrJobs
                
            self.logger.info("Total combined records: {0}".format(dfJoined.shape[0]))
        else:
            self.logger.debug("'dfJobsOnFile' is null.")
    
        return dfJoined

    def updateWorksheet(self, dfNewJobs):
        success = False
        
        if self.isLoaded():
            dfJobsOnFile = self.loadJobsFromWorksheet()
    
            # Convert new jobs to proper date-time for panda frame
            if dfNewJobs is not None and dfNewJobs.shape[0] > 0:
                dfNewJobs["posted_date"] = pd.to_datetime(dfNewJobs["posted_date"])
                dfNewJobs["updated_date"] = pd.to_datetime(dfNewJobs["updated_date"])
                # Fix date formatting to make it compatible with gsheets
                dfNewJobs["posted_date"] = dfNewJobs["posted_date"].apply(lambda d: self.utilities.getDateStr(d, GetISODateFormatStr))
                dfNewJobs["updated_date"] = dfNewJobs["updated_date"].apply(lambda d: self.utilities.getDateStr(d, GetISODateFormatStr))
                # Deal with UUID serialization issue
                dfNewJobs["id"] = dfNewJobs["id"].apply(lambda d: str(d))
            
            dfCombinedJobs = self.combineResults(dfJobsOnFile, dfNewJobs)
        
            # If able to load the worksheet
            if dfJobsOnFile is not None and dfCombinedJobs is not None:
                # Let's flag duplicates across search as opposed to removing them.
                # This can provide insights on behavior of specific companies, linkedin, etc.
                dfUniqueJobs = self.flagDuplicates(dfCombinedJobs)
        
                # Final sort for user. 
                # TODO: replace last field with keyword match score using Bert or another algorithm.
                dfUniqueJobs.sort_values(by=["posted_date", "state", "placename", "title", "company", "orig_order"], 
                                         ascending = [False, True, True, True, True, True], inplace= True)
           
                set_frozen(self.worksheet, rows=1)
                set_row_height(self.worksheet, "2:1000", 150)
                
                self.logger.info("Writing {0} jobs".format(dfUniqueJobs.shape[0]))
                outJobs = [dfUniqueJobs.columns.values.tolist()] + dfUniqueJobs.values.tolist()
                self.worksheet.update(outJobs, value_input_option = "USER_ENTERED")
    
                success = True
            else:
                self.logger.error("Unable to update job search results and persist to sheets.")
    
        return success