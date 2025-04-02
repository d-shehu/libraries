from datetime import date
import uuid
import yake

from .utilities import *

# Careful about changing this list since it affects logic in flag duplicates
# Essentially a job posting is considered unique if the location, company, job title or
# posted date differ from others. For posted date, the assumption is if a job is reposted 
# at a different date then it should be reconsidered.
def fnGetIDColumns():
    return ["country", "state", "county", "placename", "company", "title", "posted_date"]

def fnIDMatchNoDate(left, right):
    # Match on all but the date. See above.
    return (    left["country"]   == right["country"]
            and left["state"]     == right["state"]
            and left["county"]    == right["county"]
            and left["placename"] == right["placename"]
            and left["company"]   == right["company"]
            and left["title"]     == right["title"]
           )
            
def fnExtractKeywords(keywordExtractor, row):
    allKeywords = ""
    try:
        lsKeywordsScores = keywordExtractor.extract_keywords(row["description"])
        for keywordScore in lsKeywordsScores:
            allKeywords = allKeywords + keywordScore[0] + ";"
    except Exception as e:
        print("Exception while processing keywords: ", e)
        
    return allKeywords

def fnProcessKeywords(df, ngramMax=3, topMax=20):
    # Extract ngrams up to 3 tokens in length
    keywordExtractor = yake.KeywordExtractor(lan="en", n=ngramMax, dedupLim=0.9, top=topMax, features=None)

    df["keywords"] = df.apply(lambda row: fnExtractKeywords(keywordExtractor, row), axis=1)

def fnGetFieldFromDetails(dictionary, field):
    value = ""
    try:
        value = dictionary[field]
    except Exception as e:
        print(f"Error: unable to get {field} from {dictionary}")
        print(e)
    return value
        
# Previously Linkedin would annotate these fields using tags.
# However, they now jam these into a couple of detail fields.
def fnFlattenFields(dfSearchResults):
    dfSearchResults["placename"] = dfSearchResults.location.apply(lambda val: fnGetFieldFromDetails(val, "placename"))
    dfSearchResults["county"] = dfSearchResults.location.apply(lambda val: fnGetFieldFromDetails(val, "county"))
    dfSearchResults["state"] = dfSearchResults.location.apply(lambda val: fnGetFieldFromDetails(val, "state"))
    dfSearchResults["country"] = dfSearchResults.location.apply(lambda val: fnGetFieldFromDetails(val, "country"))
    
    return dfSearchResults

def fnFormatJobRecords(dfSearchResults):
    updateDate = date.today()

    # Flatten dictionaries into fields in dataframe
    fnFlattenFields(dfSearchResults)
    
    # Remove duplicates from search results using the ID columns
    print("Info: {0} jobs to clean up.".format(dfSearchResults.shape[0]))
    dfUniqueResults = dfSearchResults.drop_duplicates(
        subset=fnGetIDColumns(), keep='first', inplace=False, ignore_index=True).reset_index(drop=True)    
    
    # Derive or assign other attributes
    dfUniqueResults["orig_order"] = dfUniqueResults.reset_index().index
    dfUniqueResults["updated_date"] = fnGetDateStr(updateDate)
    dfUniqueResults["id"] = dfSearchResults.title.apply(lambda val: uuid.uuid4()) # Generate a unique id for each record
    dfUniqueResults["status"] = "TODO" # Set status of newly found jobs to "TODO"
    
    # Select and reorder only those fields that are relavent
    lsColsReordered = ["posted_date", "updated_date", "id", "placename", "county", "state", "country", "title", "company", 
                       "status", "apply_url", "company_url", "work_model", "description", "employment_type", 
                       "orig_order", "posted"]
    dfJobs = dfUniqueResults.loc[:, lsColsReordered]

    # Extract keywords from job description
    fnProcessKeywords(dfJobs)
    
    print("Info: {0} jobs retained.".format(dfJobs.shape[0]))

    return dfJobs