import pandas as pd
import gspread
from gspread_formatting import *
from oauth2client.service_account import ServiceAccountCredentials
import os

from .format import *
from .utilities import *

def fnAuthorizeGoogleSheets(credentialsFilepath):
    gsheetsClient = None
    
    scope = ["https://www.googleapis.com/auth/spreadsheets",
             "https://www.googleapis.com/auth/drive"]

    try:
        credentials = ServiceAccountCredentials.from_json_keyfile_name(credentialsFilepath, scope)
        gsheetsClient = gspread.authorize(credentials)
    except Exception as e:
        print("Error: unable to get access to Google sheets.")
        print(e)

    return gsheetsClient

def fnFlagDuplicates(df):
    dfUpdated = df
    updatedCount = 0
    # Flag duplicate based on columns which uniquely identify a job posting.
    # Logic is slightly modified to account for jobs being reposted periodically
    # So consider any job to be a duplicate if it was posted within 1 month period
    # of the first assuming all matches.
    # Return copy of data frame if modified
    if df.shape[0] > 1:
        idColumns = fnGetIDColumns()
    
        dfSorted = df.sort_values(by=idColumns)
    
        firstDate = fnGetDateFromStr(dfSorted.loc[0, "posted_date"], fnGetISODateFormatStr)
    
        for i in range(1, dfSorted.shape[0]):
            prev = dfSorted.iloc[i-1]
            curr = dfSorted.iloc[i]
            
            if fnIDMatchNoDate(prev, curr):
                # Calculate the number of days elapsed since this was "reposted" potentially.
                days = (fnGetDateFromStr(curr["posted_date"], fnGetISODateFormatStr) - firstDate).days
                if days < 30:
                    # Let's avoid overriding if status was explicitly modified:
                    status = curr["status"]
                    if status != "Apply" and status != "Closed" and status != "Assess" and status != "Discard" and status != "Duplicate":
                        dfSorted.at[i, "status"] = "Duplicate"
                        updatedCount += 1
                # After 30 days let's assume it's a different job or worth revisiting
                else:
                    firstDate = fnGetDateFromStr(dfSorted.loc[i, "posted_date"], fnGetISODateFormatStr)
            # Different job
            else:
                firstDate = fnGetDateFromStr(dfSorted.loc[i, "posted_date"], fnGetISODateFormatStr)
                
        dfUpdated = dfSorted
        
        print("Info: Duplicates: ", updatedCount)
    else:
        print("Warning: trying to remove duplicates from dataframe with 0 or 1 rows")
        
    return dfUpdated

def fnLoadWorksheetFromGoogleDrive(gsheetsClient, url, worksheetLabel):
    worksheet = None

    try:
        # Assume the spreadsheet exists and has a tab "Search"
        sheet = gsheetsClient.open_by_url(url)
        # Read the spreadsheet into a date frame. Assume there is a tab "Search" with all search results.
        worksheet = sheet.worksheet(worksheetLabel)
        
    except Exception as e:
        print(f"Error: unable to load worksheet {worksheetLabel} at {url}")
        print(e)
    
    return worksheet

def fnLoadJobsFromWorksheet(worksheet):
    dfJobsOnFile = None

    try:
        # TODO: consider if the list gets too large for in-memory processing
        recordsOnFile = worksheet.get_all_records()
        if recordsOnFile != []:
            dfJobsOnFile = pd.DataFrame(recordsOnFile)
        else:
            dfJobsOnFile = pd.DataFrame()
    
        print("Info: Records on file: ", dfJobsOnFile.shape[0])
    except Exception as e:
        print("Error: unable to load jobs search results from Google sheets.")

    return dfJobsOnFile

def fnCombineResults(dfJobsOnFile, dfCurrJobs):
    dfJoined = None
    if dfJobsOnFile is not None:
        if (dfJobsOnFile.shape[0] > 0 and dfCurrJobs.shape[0] > 0):
            print("Info: Combining records on file with new entries")
            # Combine on file records with new entries. On file take precedence over new if duplicates are found.
            # This resumes only exact duplicates. See below for flagging duplicates posted on different dates.
            dfUnion = pd.concat(objs = [dfJobsOnFile,dfCurrJobs], axis = 0, join = "outer", ignore_index = True, keys = None)
            dfJoined = dfUnion.drop_duplicates(subset=fnGetIDColumns(), keep='first', inplace=False, ignore_index=True)
            dfJoined = dfJoined.reset_index(drop=True)
        elif dfJobsOnFile.shape[0] > 0:
            # No new jobs
            print("Info: No new jobs")
            dfJoined = dfJobsOnFile
        else:
            print("Info: No jobs on file")
            dfJoined = dfCurrJobs
            
        print("Info: Total combined records: ", dfJoined.shape[0])
    else:
        print("Error: dfJobsOnFile is null.")

    return dfJoined

# Connect to Google Sheets. Assume the secret file is at this location.
# Also assumes there is a service account associated with secret which has read/write permission
# on sheet.
def fnUpdateWorksheet(spreadsheetURL, worksheet, dfNewJobs):
    success = False
    
    gsheetsClient = fnAuthorizeGoogleSheets(os.path.expanduser("~/.secrets/jobsearch/gsheets_secrets.json"))
    if gsheetsClient is not None:
        worksheet = fnLoadWorksheetFromGoogleDrive(gsheetsClient, spreadsheetURL, worksheet)
        dfJobsOnFile = fnLoadJobsFromWorksheet(worksheet)

        # Convert new jobs to proper date-time for panda frame
        if dfNewJobs is not None and dfNewJobs.shape[0] > 0:
            dfNewJobs["posted_date"] = pd.to_datetime(dfNewJobs["posted_date"])
            dfNewJobs["updated_date"] = pd.to_datetime(dfNewJobs["updated_date"])
            # Fix date formatting to make it compatible with gsheets
            dfNewJobs["posted_date"] = dfNewJobs["posted_date"].apply(lambda d: fnGetDateStr(d, fnGetISODateFormatStr))
            dfNewJobs["updated_date"] = dfNewJobs["updated_date"].apply(lambda d: fnGetDateStr(d, fnGetISODateFormatStr))
            # Deal with UUID serialization issue
            dfNewJobs["id"] = dfNewJobs["id"].apply(lambda d: str(d))
        
        dfCombinedJobs = fnCombineResults(dfJobsOnFile, dfNewJobs)
    
        # If able to load the worksheet
        if dfJobsOnFile is not None and dfCombinedJobs is not None:
            # Let's flag duplicates across search as opposed to removing them.
            # This can provide insights on behavior of specific companies, linkedin, etc.
            dfUniqueJobs = fnFlagDuplicates(dfCombinedJobs)
    
            # Final sort for user. 
            # TODO: replace last field with keyword match score using Bert or another algorithm.
            dfUniqueJobs.sort_values(by=["posted_date", "state", "placename", "title", "company", "orig_order"], 
                                     ascending = [False, True, True, True, True, True], inplace= True)
       
            set_frozen(worksheet, rows=1)
            set_row_height(worksheet, "2:1000", 150)
            
            print("Info: Writing {0} jobs".format(dfUniqueJobs.shape[0]))
            outJobs = [dfUniqueJobs.columns.values.tolist()] + dfUniqueJobs.values.tolist()
            worksheet.update(outJobs, value_input_option = "USER_ENTERED")

            success = True
        else:
            print("Error: unable to update job search results and persist to sheets.")

    return success