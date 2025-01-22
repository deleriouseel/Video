
import requests
import re
import time
import os
from datetime import date, timedelta
import logging
import logging.handlers
from random import *


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    filename=r".\subsplash.log",
)


url = "https://dashboard.subsplash.com/"
values = {
    "username": os.environ.get("SUBSPLASH_USERNAME"),
    "password": os.environ.get("SUBSPLASH_PASSWORD"),
}

mydate = date.today()


def open_session():
    global session
    global response
    global url

    # open session
    session = requests.session()
    logging.info("Opening session")

    # log in
    response = session.post(url + "/login", data=values, allow_redirects=True)
    logging.debug("Login response: " + response.url)
    #logging.info("Checking for email verification")
    #verifylink = verifyEmailGraph()
    #response = session.get(verifylink, allow_redirects=True)
    logging.info(response.request.headers)
    logging.info(response.url)

    # go to analytics page
    time.sleep(15)
    response = session.get(url + "/-d/#/media/bulk-import-edit", timeout=20)
    logging.info(response.url)

    return response
from datetime import date, timedelta

def get_friday():
    today = date.today()
    offset = (today.weekday() - 4) % 7
    previous_friday = today - timedelta(days=offset)
    return previous_friday.isoformat()

def get_monday():
    today = date.today()
    offset = (today.weekday() - 0) % 7
    previous_monday = today - timedelta(days=offset)
    return previous_monday.isoformat()


# TODO Get CSV from 
start_date = get_friday()
end_date = get_monday()
link= f"https://core.subsplash.com/media/v1/media-items-metadata?filter%5Bapp_key%5D=FMJKKH&filter%5Bstart_date%5D=2025-01-03&filter%5Bend_date%5D=2025-01-14"
print(link)

def download_csv(session, link):
    response = session.get(link)
    if response.status_code == 200:
        logging.info("Successfully downloaded the response")
        return response.content
    else:
        logging.error(f"Failed to download the response, status code: {response.status_code}")
        return None
# TODO Get vimeo json. return vimeo_repsonse
# TODO Match CSV column 1 against vimeo_response['name']

# Find the HLS link
# hls_link = None
# for file in vimeo_response['files']:
#     if file['quality'] == 'hls':
#         hls_link = file['link']
#         break

# replace_end = hls_link.find("&oauth2_token_id=")
# # Replace everything from `&oauth2_token_id` onward with `&logging=false`
# if replace_end != -1:
#     updated_url = hls_link[:replace_end] + "&logging=false"
#     # TODO Put updated_url into CSV column I (9)
# else:
#     #TODO Error out
#     print("No oauth token id found")

# TODO Upload file back to subsplash

open_session()