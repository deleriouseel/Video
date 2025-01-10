
import requests
import re
import time
import os
from datetime import date
import logging
import logging.handlers
from random import *


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    filename=r"C:\Users\AudioVisual\Documents\GitHub\Video\filename.log",
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
    logging.info("Checking for email verification")
    #verifylink = verifyEmailGraph()
    response = session.get(verifylink, allow_redirects=True)
    logging.info(response.request.headers)
    logging.info(response.url)

    # go to analytics page
    time.sleep(15)
    response = session.get(url + "/analytics/", timeout=20)
    logging.info(response.url)

    return response


# TODO Get CSV from https://dashboard.subsplash.com/-d/#/media/v1/media-items-metadata?filter%5Bapp_key%5D=FMJKKH&filter%5Bstart_date%5D=2024-10-17&filter%5Bend_date%5D=2024-10-23
# TODO Get vimeo json. return vimeo_repsonse
# TODO Match CSV column 1 against vimeo_response['name']

# Find the HLS link
hls_link = None
for file in vimeo_response['files']:
    if file['quality'] == 'hls':
        hls_link = file['link']
        break

replace_end = hls_link.find("&oauth2_token_id=")
# Replace everything from `&oauth2_token_id` onward with `&logging=false`
if replace_end != -1:
    updated_url = hls_link[:replace_end] + "&logging=false"
    # TODO Put updated_url into CSV column I (9)
else:
    #TODO Error out
    print("No oauth token id found")

# TODO Upload file back to subsplash