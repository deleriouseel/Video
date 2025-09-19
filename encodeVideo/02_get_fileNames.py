'''
Get filenames from WordPress posts and rename .mov files accordingly.
Modified to match files using only month and day.
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

# Get filenames from WP and store by month/day tuple
for post in posts:
    post_date = datetime.strptime(post['date'], '%Y-%m-%dT%H:%M:%S').date()
    # Create a tuple of (month, day) for matching
    month_day = (post_date.month, post_date.day)
    logging.debug(f"Post date: {post_date}, Month/Day: {month_day}")
    
    content = post['content']['rendered']
    match = pattern.search(content)
    if match:
        filename = match.group(1)
        logging.debug(f"Filename: {filename}")
        # Use month/day tuple as the key for matching
        post_dates[month_day] = {
            'filename': filename,
            'original_date': post_date
        }

logging.debug(f"Post dates by month/day: {post_dates}")

# Get .mov files and their media properties
files = [f for f in os.listdir(folder) if f.endswith('.MOV')]
logging.debug(f"Found .MOV files: {files}")
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
                # Store both full date and month/day tuple
                month_day = (media_created_date.month, media_created_date.day)
                file_dates[file] = {
                    'full_date': media_created_date,
                    'month_day': month_day
                }
                logging.debug(f"{file}: Media Created Date - {media_created_date}, Month/Day: {month_day}")

# Rename files
for file, file_info in file_dates.items():
    month_day = file_info['month_day']
    full_date = file_info['full_date']
    
    if month_day in post_dates:
        file_extension = os.path.splitext(file)[1]
        new_file_name = post_dates[month_day]['filename'] + 'V' + file_extension
        new_file_path = os.path.join(folder, new_file_name)
        old_file_path = os.path.join(folder, file)

        os.rename(old_file_path, new_file_path)
        logging.info(f"Renamed: {file} to {new_file_name}")
        logging.info(f"Matched file date {full_date} with post date {post_dates[month_day]['original_date']} (both {month_day[0]}/{month_day[1]})")
    else:
        logging.error(f"No matching post date for file: {file} (date: {full_date}, month/day: {month_day[0]}/{month_day[1]})")
        # Log available month/day combinations for debugging
        available_month_days = list(post_dates.keys())
        logging.debug(f"Available post month/day combinations: {[(md[0], md[1]) for md in available_month_days]}")