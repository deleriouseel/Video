import logging
import requests
import os
import vimeo
import re
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    filename=r"C:\Users\AudioVisual\Documents\GitHub\Video\filename.log",
)

url = os.getenv("WP_API_URL") + "posts?categories=48&per_page=3"
username = os.getenv("WP_API_USER")
password = os.getenv("WP_API_PASSWORD")
headers = {
    "Accept": "*/*",
    "Content-Type": "application/json",
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
}

client = vimeo.VimeoClient(
      token=os.getenv('VIMEO_TOKEN'),
      key=os.getenv("VIMEO_KEY"),
      secret=os.getenv("VIMEO_SECRET"),
    )

# Get 3 vimeo video ids
def getVideoInfo():
  
  logging.info("Beginning getVideoInfo")

  try:
    video_info = client.get(f'/users/75458348/videos', params={
        'sort': 'date',
        'direction': 'desc',
        'per_page': 3
    }).json()

    if video_info:
        #logging.debug(video_info)
        logging.info("Returning video_info")
        return video_info['data']
    else:
        logging.error("No video found")
        return []
    
  except Exception as e:
        logging.error(f"Failed to retrieve video info: {e}")

# Get 3 wordpress posts
def getWordpressInfo():
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        posts = response.json()
    except Exception as e:
        logging.error(f"Failed to retrieve WordPress posts: {e}")
        return [], []
    
    pattern = re.compile(r'https://media\.northcountrychapel\.com/rafiles/([a-zA-Z0-9-]+)\.mp3')
    # Dictionary to hold post filenames and titles
    titles = []
    filenames = []
    
    for post in posts:
        content = post['content']['rendered']
        match = pattern.search(content)
        if match:
            filename = match.group(1)  # Extract filename without extension
            filenames.append(filename)
            titles.append(post['title']['rendered'])


    logging.info(f"Titles: {titles}")
    logging.info(f"Filenames: {filenames}")
    return titles, filenames

# Iterate through each video and patch with post_title
# Send patch to vimeo
def update_vimeo_titles(videos, titles, filenames):
    for video in videos:
        current_title = video['name']
        logging.debug(f"Current title: {current_title}")
        
        # Check if the video title matches any filename
        file_name = current_title.replace('V.mp4', '').strip()
        logging.debug(f"File name: {file_name}")
        
        # Find the corresponding WordPress title
        if file_name in filenames:
            logging.debug(f"Comparing file_name: '{file_name}' with filenames: {filenames}")
            index = filenames.index(file_name)
            matching_title = titles[index]
            logging.debug(f"Matching title from WordPress: {matching_title}")

            # Payload for the PATCH request
            payload = {'name': matching_title}
            logging.debug(f"Payload for PATCH request: {payload}")

            # Update the Vimeo title
            client.patch(video['uri'], json=payload)
            logging.info(f"Changed {file_name} to {matching_title}")


def main():
    latest_videos = getVideoInfo()
    latest_wordpress_titles, latest_wordpress_filenames = getWordpressInfo()
    update_vimeo_titles(latest_videos, latest_wordpress_titles, latest_wordpress_filenames)

if __name__ == '__main__':
    main()