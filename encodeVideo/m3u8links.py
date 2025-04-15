import os
import logging
import datetime
import json
import vimeo
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
today = str(datetime.date.today())
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    filename=f"vimeo_m3u8_extractor_{today}.log",
)

def get_m3u8_links():
    """
    Get the m3u8 links for the latest videos and save them to text file
    """
    client = vimeo.VimeoClient(
        token=os.getenv('VIMEO_TOKEN'),
        key=os.getenv("VIMEO_KEY"),
        secret=os.getenv("VIMEO_SECRET"),
    )
    logging.info("Getting latest videos from Vimeo")
    
    # Create a list to store all the links and information
    all_links = []

    try:
        # Get the latest videos (default: 3)
        response = client.get(f'/users/75458348/videos', params={
            'sort': 'date',
            'direction': 'desc',
            'per_page': 3
        })
        
        # Parse the response
        videos_data = response.json()
        
        # Process each video
        for video in videos_data['data']:
            video_id = video["uri"].split('/')[-1]
            video_title = video["name"]
            
            logging.info(f"Processing video: {video_title} (ID: {video_id})")
            
            # Find the m3u8 link in the files array
            m3u8_link = None
            
            for file_info in video["files"]:
                if file_info.get("quality") == "hls" and "link" in file_info:
                    # Get the original m3u8 link
                    original_link = file_info["link"]
                    
                    # Replace oauth2_token_id parameter with logging=false
                    if "oauth2_token_id=" in original_link:
                        m3u8_link = original_link.split("oauth2_token_id=")[0] + "logging=false"
                    else:
                        m3u8_link = original_link
                        
                    logging.info(f"Original m3u8 link: {original_link}")
                    logging.info(f"Modified m3u8 link: {m3u8_link}")
                    break
            
            if m3u8_link:
                # Add the video info and link to our list
                all_links.append({
                    "video_id": video_id,
                    "title": video_title,
                    "link": m3u8_link
                })
            else:
                logging.error(f"No m3u8 link found for video: {video_title}")
        
        # Save all links to a single file
        if all_links:
            save_links_to_file(all_links)
    
    except Exception as e:
        logging.error(f"Error getting videos: {e}")
        return None

def save_links_to_file(links_data):
    """
    Save all m3u8 links to the desktop
    """
    try:
        # Get desktop path
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        file_path = os.path.join(desktop_path, f"vimeo_m3u8_links_{today}.txt")
        
        with open(file_path, 'w') as f:
            for item in links_data:
                # Write video title and ID as a comment line
                f.write(f"# {item['title']} (ID: {item['video_id']})\n")
                # Write the m3u8 link
                f.write(f"{item['link']}\n\n")
        
        logging.info(f"Saved all m3u8 links to {file_path}")
        return file_path
    except Exception as e:
        logging.error(f"Error saving links to file: {e}")
        return None

if __name__ == "__main__":
    logging.info("Starting Vimeo m3u8 link extractor")
    get_m3u8_links()
    logging.info("Completed extraction process")