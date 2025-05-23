'''
Get filenames from WordPress posts and rename .mov files accordingly.
'''
import logging
import requests
import re
import os
from datetime import datetime
from dotenv import load_dotenv
from pymediainfo import MediaInfo

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    filename=r"C:\Users\AudioVisual\Documents\GitHub\Video\filename.log",
)

folder = r'C:\Users\AudioVisual\Desktop'
url = os.getenv("WP_API_URL") + "posts?categories=48&per_page=3"
username = os.getenv("WP_API_USER")
password = os.getenv("WP_API_PASSWORD")
headers = {
    "Accept": "*/*",
    "Content-Type": "application/json",
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
}

response = requests.get(url, headers=headers)
posts = response.json()

# Match the filename in the URL
pattern = re.compile(r'https://media\.northcountrychapel\.com/rafiles/([a-zA-Z0-9-]+)\.mp3')

post_dates = {}

# Get filenames from WP
for post in posts:
    post_date = datetime.strptime(post['date'], '%Y-%m-%dT%H:%M:%S').date()
    logging.debug(post_date)
    content = post['content']['rendered']
    match = pattern.search(content)
    if match:
        filename = match.group(1)
        logging.debug(filename)
        post_dates[post_date] = filename

logging.debug(post_dates)

# Get .mov files and their media properties
files = [f for f in os.listdir(folder) if f.endswith('.MOV')]
logging.debug(files)
file_dates = {}

for file in files:
    file_path = os.path.join(folder, file)
    media_info = MediaInfo.parse(file_path)

    for track in media_info.tracks:
        if track.track_type == "General":
            encoded_date_str = track.encoded_date
            if encoded_date_str:
                # Convert to date object
                media_created_date = datetime.strptime(encoded_date_str, '%Y-%m-%d %H:%M:%S %Z').date()
                file_dates[file] = media_created_date
                logging.debug(f"{file}: Media Created Date - {media_created_date}")

# Rename files
for file, file_date in file_dates.items():
    if file_date in post_dates:
        file_extension = os.path.splitext(file)[1]
        new_file_name = post_dates[file_date] + 'V' + file_extension
        new_file_path = os.path.join(folder, new_file_name)
        old_file_path = os.path.join(folder, file)

        os.rename(old_file_path, new_file_path)
        logging.info(f"Renamed: {file} to {new_file_name}")
    else:
        logging.error(f"No matching post date for file: {file}")
