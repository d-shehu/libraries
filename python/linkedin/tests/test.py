import acquire
import authenticate
import format
import job_search
import queries
import utilities

# Test code
print(fnParsePosted("3 month ago", date.today()))

# queries
fnGetGeoIDFromLocation(gScraper, "New York", "New York", "United States")
fnGetQuery(gScraper, "Technical Program Manager", {"city": "New York", "state": "New York", "radius": 5}, "week")


# Acquire
# Test code
#jobUrl="https://www.linkedin.com/jobs/view/4131838543/?eBP=CwEAAAGVbGa7Q4RB_LVnO7tt-I3npV1y4i8IWqhQ1_4Jt6VR0g7kNZYGfYhsTuCm-xYfeBXBL_CvaSeAu9Tke4Sk0tEKl8DJoCrFLYybQFRes1msQl7wm2RSft1DyaowofhK-xRPC4MeKF99stcfPI_svXLgbEJWyRzgP1xlu2-ULil5vwEQlwTefjli1Uss_D1DibmE4T-0dPuXBSD49JsjNpKemfvtDj5kdA7SAp4LDv2Y1gIYJpZ7hgWs64OoXiUWO5_b2buj0kbnqNNVitECgtpoZguDDn6t7Aoiq88js2UgSMMjxq_pc2PlVReNU_1XE18tYUardQvBCgLa15Xc3cyThzJ77fNvpUc_2ziq4BUL3rmJKzuZpOcM367swCpO9gohdjHugc6CxsgnmeMJi-QRdqIY6Hk4Ub1avKGDcYM1kfLzOb6GuuMLJw-Ta__nWmV0VLaAdJGFYGMONi4al6F56B7B-sAwpMngkhF-pu2xA0gXt3-eOTnR1GrzajWgwYwleTR_oap5gQ&refId=hZW%2FR8A9ehqAHOvq1p8YUg%3D%3D&trackingId=edeX66PJUST12r2BLtXwbw%3D%3D"
#gScraper.loadPage(jobUrl)
#url = fnGetLinkFromButton(gScraper)
#print("URL: ", url)

# Test Code
# ollamaClient = fnConnectToClient()
#url = "https://www.linkedin.com/jobs/view/4150184214/?eBP=CwEAAAGVcxZ9SVQeE1jE3eLpyxOL4TTjkZqtnWJbcbKPadZg0NqwHA_9Z5scFefH3tynF1L-kDWFdOMtLCov2pUNJNTuOmJ2Dod9rDSbuAJLg7ZjdoWm2DztE57UE6dRMpVSyrQpz--gYEpbGka1_fBB9QLIpQDCFOGlypWTgSt0doraRJ9ycdAyPJlV-reMF1En3lShPP6ZrsxMliPzg04X0ZTpILO3hQrLFu5NoigfiBBebmK-m41W1Q_h9Mq1GOhnvvjXfL4zRnjnYcqox4woWFuL06zNgQkYBJIhmbeZxWkuh9r4FzEFlw-imLYJcwYlbAlfNlp8akycQ7FMJZWG61JiU-X95tUAaOGoC6X_6KVnlvuYrnFTpaZy34FQOam0Umdz506HovXio-QbQsMK8wKWX9z2GHZ93TfKkQK0zCqPopgWmzRjk8Bau-H7_KIW4kLuNhCcsVa9a9lpbFvt4HT6yZzcfaERBHKmzZxff3_1ihY-9Y-DqUpYI8udDyND5iG0-Q&refId=Xi7yHmeqFoAUq7V0siftcQ%3D%3D&trackingId=6Wnk3LSrg3G00ZgOFZr8Qw%3D%3D&trk=flagship3_search_srp_jobs"
#job = {}
#job["url"] = url
#fnParseJobDetails(gScraper, job)

# Test Code
#testList = []
#url = fnGetQuery(gScraper, "Technical Program Manager", {"city": "New York", "state": "New York", "radius": 5}, "week")
#listJobs = fnGetJobs(gScraper, url, testList)
#fnProcessJobs(gScraper, testList)

# Test code
#testList = []
#url = fnGetQuery(gScraper, "Technical Program Manager", {"city": "New York", "state": "New York", "radius": 5}, "week")
#fnGetJobs(gScraper, url, testList)
#fnGetJobs(gScraper, "https://www.linkedin.com/jobs/collections/recommended", testList, JobsMode.RECOMMENDATIONS)

# Test code
#testListJobs = []
#testURL = fnGetQuery(gScraper, "Technical Program Manager", {"city": "New York", "state": "New York", "radius": 25}, "week")
#fnFetchJobs(gScraper, testURL, testListJobs)
#fnFetchJobs(gScraper, "https://www.linkedin.com/jobs/collections/recommended", testListJobs, JobsMode.RECOMMENDATIONS)


# Test code
#print(fnGetFieldsFromDetails(dfCurrSearchResults))


# Test code
#testRoles = [ "Technical Program Manager" ]
#testLocations = [ {"city": "New York", "state": "New York", "radius": 5} ]
#fnSearch(gScraper, testRoles, testLocations, timespan = "week")


# Test code
#fnGetRecommendations(gScraper)

# Test code
#print(fnFormatJobRecords(dfCurrSearchResults))


lsJobDetails = ['Atlanta, GA', ' · ', 'Reposted 5 hours ago', ' · ', 'Over 100 people clicked apply', 
                '$119.7K/yr - $146.2K/yr', 'Hybrid', 'Full-time']

lsJobDetails = ['Las Vegas, NV', ' · ', '20 hours ago', ' · ', '18 people clicked apply', 'On-site', 'Full-time']

lsJobDetails = ['United States', ' · ', '17 hours ago', ' · ', 'Over 100 people clicked apply', 'Remote', 'Full-time']

#lsJobDetails = ['New York, NY', ' · ', 'Reposted 4 hours ago', ' · ', '6 applicants', 'Hybrid', 'Full-time']

#lsJobDetails = ['Rochester, NY', ' · ', '1 hour ago', ' · ', '1 person clicked apply', 'On-site', 'Full-time']

lsJobDetails = ['Farmingdale, NY', ' · ', 'Reposted 9 hours ago', ' · ', '15 people clicked apply', '$82K/yr - $136.7K/yr', 
                'On-site', 'Full-time' ]

#lsJobDetails = ['Texas, United States', ' · ', 'Reposted 13 hours ago', ' · ', 'Over 100 people clicked apply', 
#                '$112K/yr - $166.1K/yr', 'Remote', 'Full-time']

#lsJobDetails = ['Arlington, VA', ' · ', '3 hours ago', ' · ', '2 people clicked apply', 'On-site', 'Full-time']

job = {}
utilities.fnParseDetails(geolocator, lsJobDetails, job)


geolocator = Nominatim(user_agent="TestAgent")

locationBogus =  geolocator.geocode("Badaddress")

print(locationBogus)

location = geolocator.geocode("New York, NY, United States")

geolocator.reverse(location.raw['lat'] + "," + location.raw['lon']).raw['address']

location.raw['lat']

location2 =  geolocator.geocode("Jackson, NJ, United States")

distance.distance((location.raw['lat'], location.raw['lon']), (location2.raw['lat'], location2.raw['lon'])).miles