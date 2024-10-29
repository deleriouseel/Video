import os
import logging
import re
import vimeo
import logging
import requests
import os
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


# Check if a video has already been uploaded
def uploadList(upload_name):
    try:
        with open('uploaded.txt', 'r') as f:
            uploaded_videos = {line.strip() for line in f}
    except FileNotFoundError:
        return False  # If the file doesn't exist, assume no videos have been uploaded

    return upload_name in uploaded_videos


def uploadVideos(directory):
    for filename in os.listdir(directory):
        if filename.endswith('.mp4'): 
            video_path = os.path.join(directory, filename)
            file_size = os.path.getsize(video_path) / (1024 * 1024 * 1024)
            
            if not (1.5 <= file_size <= 5):
                logging.info(f"{filename} is not between 1.5 GB - 5 GB. Skipping...")
                continue
            upload_name = os.path.splitext(filename)[0]

            if uploadList(upload_name):
                logging.info(f"{upload_name} has already been uploaded. Skipping...")
                continue
            
            uploadVimeo(video_path, upload_name)

#Check if video is in uploaded.txt, if not, upload to Vimeo
# Then patch video title to match WP post title
def uploadVimeo(video_path, upload_name):
    client = vimeo.VimeoClient(
        token=os.getenv('VIMEO_TOKEN'),
        key=os.getenv("VIMEO_KEY"),
        secret=os.getenv("VIMEO_SECRET"),
    )

    logging.info("Starting uploadVimeo")
    logging.debug(f"Incoming upload_name: {upload_name}")
    logging.info(f"Starting upload for {os.path.basename(video_path)}")

    # Read existing uploaded videos
    uploaded_files = set()
    if os.path.exists('uploaded.txt'):
        with open('uploaded.txt', 'r') as f:
            uploaded_files = set(line.strip() for line in f)

    # Check if the video has already been uploaded
    original_filename = os.path.basename(video_path)
    if original_filename in uploaded_files:
        logging.info(f"{original_filename} has already been uploaded. Skipping...")
        return None

    tags = ["northcountrychapel", "ncc", "biblestudy"]
    regex = r'\b(?:[1-3]?\s?[a-zA-Z]+\s?[A-Za-z]*)\b'
    #book_name = re.search(regex, upload_name).group(0) if re.search(regex, upload_name) else "unknown"

    try:
        # Upload video
        uri = client.upload(video_path, data={
            'name': upload_name,
            'privacy': {
                'view': 'anybody'
            },
            'content-rating': 'safe',
            'license': 'by-nc-sa',
            'tags': tags,
        })

        logging.info(f"Finished upload. Video uri is {uri}")
        video_id = uri.split('/')[-1]

        # Update the title
        patch_data = {
            'name': upload_name  
        }
        response = client.patch(f'/videos/{video_id}', data=patch_data)

        if response.status_code == 200:
            logging.info(f"Title updated successfully to: {upload_name}")

            # Append the original filename to uploaded.txt
            with open('uploaded.txt', 'a') as f:
                f.write(f"{original_filename}\n")
        else:
            logging.error(f"Failed to update the title. Response: {response.json()}")

        return uri

    except Exception as e:
        logging.error(f"An error occurred during the upload: {str(e)}")
        return None

def getPost(url):
    logging.info("Getting post from wordpress api")
    response = requests.get(url,headers=headers)
    if response.status_code == 200:
        post = response.json()[0]
        return post
    else:
        logging.error(f"Error: {response.status_code} - {response.reason}")   

      

def getName(post):
    logging.info("Getting file name from wordpress post")
    post_date = post['date']
    post_date = datetime.strptime(post_date, "%Y-%m-%dT%H:%M:%S").date()
    today = datetime.today().date()

    if post_date == today:
        post_title = post["title"]["rendered"]
        logging.info(post_title)
        return post_title
    else:
        logging.error("No post matching today's date found. Returning today's date.")
        return str(today)


# Call the function with the target directory
# uploadVimeo(r'D:\Studies')

if __name__ == "__main__":
    uploadVideos(r"D:\Studies")