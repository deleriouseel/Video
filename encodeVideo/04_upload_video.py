import os
import logging
import vimeo
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
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

logging.info("Starting upload_video.py")

# Check if a video has already been uploaded
def uploadList(upload_name):
    try:
        with open('uploaded.txt', 'r') as f:
            uploaded_videos = {line.strip() for line in f}
    except FileNotFoundError:
        return False  # If the file doesn't exist, assume no videos have been uploaded

    return upload_name in uploaded_videos


def uploadVideos(directory):
    
    uploaded_files = set()
    if os.path.exists('uploaded.txt'):
        with open('uploaded.txt', 'r') as f:
            uploaded_files = {line.strip() for line in f}

    # Iterate through files in D:/Studies
    for filename in os.listdir(directory):
        if filename.endswith('.mp4'): 
            video_path = os.path.join(directory, filename)
            file_size = os.path.getsize(video_path) / (1024 * 1024 * 1024) 
            
            
            if not (1.5 <= file_size <= 5):
                logging.info(f"{filename} is not between 1.5 GB - 5 GB. Skipping...")
                continue
            
            upload_name = filename 

            # Check if this video has already been uploaded 
            if upload_name in uploaded_files:
                logging.info(f"{upload_name} has already been uploaded. Skipping...")
                continue
            
            # Upload the video to Vimeo
            if uploadVimeo(video_path, upload_name):
                # After successful upload, add the filename to the uploaded list
                with open('uploaded.txt', 'a') as f:
                    f.write(f"{upload_name}\n")



#Check if video is in uploaded.txt, if not, upload to Vimeo
def uploadVimeo(video_path, upload_name):
    client = vimeo.VimeoClient(
        token=os.getenv('VIMEO_TOKEN'),
        key=os.getenv("VIMEO_KEY"),
        secret=os.getenv("VIMEO_SECRET"),
    )

    logging.info("Starting uploadVimeo")
    logging.debug(f"Incoming upload_name: {upload_name}")
    logging.info(f"Starting upload for {os.path.basename(video_path)}")

    try:
        # Upload video to Vimeo
        uri = client.upload(video_path, data={
            'name': upload_name,
            'privacy': {
                'view': 'anybody'
            },
            'content-rating': 'safe',
            'license': 'by-nc-sa',
            'tags': ["northcountrychapel", "ncc", "biblestudy"],
        })

        logging.info(f"Finished upload. Video URI is {uri}")
        video_id = uri.split('/')[-1]

    except Exception as e:
        logging.error(f"An error occurred during the upload: {str(e)}")
        return False  # Indicate failure in uploading


# Call the function with the target directory

if __name__ == "__main__":
    uploadVideos(r"D:\Studies")