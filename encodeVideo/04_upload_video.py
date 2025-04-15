'''
Uploads videos to Vimeo from D:/Studies
Only uploads videos that are newer than the previous Thursday
'''
import os
import logging
import vimeo
import datetime
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    filename=r"C:\Users\AudioVisual\Documents\GitHub\Video\filename.log",
)
logging.info("Starting upload_video.py")

def getThursday():
    # Get today's date
    today = datetime.today()
    # Calculate the days since Thursday
    days_since_thursday = (today.weekday() - 3 + 7) % 7
    
    # If today is Thursday, we want last week's Thursday
    if days_since_thursday == 0:
        days_since_thursday = 7
    
    previous_thursday = today - timedelta(days=days_since_thursday)
    previous_thursday = previous_thursday.replace(hour=0, minute=0, second=0, microsecond=0)
    
    logging.info(f"Previous Thursday: {previous_thursday}")
    return previous_thursday

def newestFiles(file_path):
    """Check if the file was modified after the previous Thursday."""
    # Get file modification time
    file_time = os.path.getmtime(file_path)
    file_date = datetime.fromtimestamp(file_time)
    
    # Get the previous Thursday
    prev_thursday = getThursday()
    
    # Check if file is newer than previous Thursday
    is_recent = file_date > prev_thursday
    
    logging.info(f"File: {os.path.basename(file_path)}, Date: {file_date}, Is Recent: {is_recent}")
    return is_recent

def uploadVideos(directory):
    # Iterate through files in D:/Studies
    for filename in os.listdir(directory):
        if filename.endswith('.mp4'): 
            video_path = os.path.join(directory, filename)
            file_size = os.path.getsize(video_path) / (1024 * 1024 * 1024) 
            
            # Check if video is newer than previous Thursday
            if not newestFiles(video_path):
                logging.info(f"{filename} is not newer than previous Thursday. Skipping...")
                continue
            
            if not (1.5 <= file_size <= 5):
                logging.info(f"{filename} is not between 1.5 GB - 5 GB. Skipping...")
                continue
            
            upload_name = filename 
            
            # Upload the video to Vimeo
            uploadVimeo(video_path, upload_name)

# Upload to Vimeo
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
        return True
    except Exception as e:
        logging.error(f"An error occurred during the upload: {str(e)}")
        return False

# Call the function with the target directory
if __name__ == "__main__":
    uploadVideos(r"D:\Studies")