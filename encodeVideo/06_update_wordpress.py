"""Update a WordPress post with Vimeo video iframe.
This fetches info about the latest WordPress posts from the "bible study" category, retrieves video id from Vimeo, and updates the WordPress post with the video embed code if the post's title matches the video title.

"""

import logging
import requests
import os
import json
import datetime
import re
from dotenv import load_dotenv
import vimeo
import html
from fuzzywuzzy import fuzz


load_dotenv()
today = str(datetime.date.today())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    filename=r"C:\Users\AudioVisual\Documents\GitHub\Video\filename.log",
)
# WP Login stuff
url = os.getenv("WP_API_URL")
username = os.getenv("WP_API_USER")
password = os.getenv("WP_API_PASSWORD")
headers = {
    "Accept": "*/*",
    "Content-Type": "application/json",
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }

logging.info("Starting update_wordpress.py")

def normalize_title(title):
    return html.unescape(title).strip().lower()

def getVideoInfo():
  client = vimeo.VimeoClient(
      token=os.getenv('VIMEO_TOKEN'),
      key=os.getenv("VIMEO_KEY"),
      secret=os.getenv("VIMEO_SECRET"),
    )
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
  except Exception as e:
        logging.error(f"Failed to retrieve video info: {e}")


def getPost(url):
    logging.info("Getting post from wordpress api")
    response = requests.get(url,headers=headers)
    if response.status_code == 200:
        post = response.json()
        return post
    else:
        logging.error(f"Error: {response.status_code} - {response.reason}")   

def updatePost():
    try:
        # Get WP info
        posts = getPost(os.getenv("WP_API_URL") + "posts?categories=48&per_page=3")
        if not posts:
            logging.error("Failed to retrieve posts from WordPress API")
            return
        
        # Get video info
        video_info = getVideoInfo()
        if not video_info:
            logging.error("Failed to retrieve video info from Vimeo")
            return

        # Iterate through each post and update if titles match
        for post in posts:
            
            post_title = normalize_title(post["title"]["rendered"])
            logging.debug(f"Normalized Post title: {post_title}")

            # Check against all Vimeo videos
            for video in video_info:
                vimeo_title = normalize_title(video["name"])
                video_id = video["uri"].split('/')[-1]  # Extract video ID from URI

                logging.debug(f"Normalized Vimeo title: {vimeo_title}")

                similarity_score = fuzz.ratio(normalize_title(post_title), normalize_title(vimeo_title))
                
                logging.debug(f"Comparing '{post_title}' to '{vimeo_title}' - Similarity Score: {similarity_score}")

                if similarity_score > 80:
                    embed_code = (f'<div style="padding:56.25% 0 0 0;position:relative;"><iframe src="https://player.vimeo.com/video/{video_id}?badge=0&amp;autopause=0&amp;player_id=0&amp;app_id=58479" frameborder="0" allow="autoplay; fullscreen; picture-in-picture; clipboard-write" style="position:absolute;top:0;left:0;width:100%;height:100%;" title="{vimeo_title}"></iframe></div><script src="https://player.vimeo.com/api/player.js"></script>')
                    
                    post_id = post["id"]
                    post_content = post["content"]["rendered"]
                    post_content = re.sub(r'[\r\n]+', '\n', post_content)

                    payload = json.dumps({
                        "content": post_content + "\n" + embed_code
                    })

                    # Update the post in WordPress
                    response = requests.put(f"{url}posts/{post_id}", headers=headers, auth=(username, password), data=payload)
                    logging.info(f"Post updated successfully: {response.text}")
                    logging.debug(f"Post updated with {embed_code}")
                    break 
            else:
                logging.debug(f"No matching video found for post: {post_title}")

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")   

   
updatePost()