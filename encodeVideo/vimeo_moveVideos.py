import re
import vimeo
import os
import logging
from dotenv import load_dotenv
import json

# Configure logging
logging.basicConfig(
    filename='vimeo_organize.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Find .env file
env_path = os.path.join("./", ".env")
load_dotenv(env_path)


client = vimeo.VimeoClient(
    token=os.getenv('VIMEO_TOKEN'),
    key=os.getenv('VIMEO_KEY'),
    secret=os.getenv('VIMEO_SECRET')
)

def get_all_folders():
    """Get all folders/projects in the Vimeo account """
    logger.info("Fetching all folders...")
    
    # Initialize variables for pagination
    all_folders = []
    page = 1
    more_pages = True
    
    while more_pages:
        # Get the current page of folders
        response = client.get('/me/projects', params={'page': page, 'per_page': 100})
        data = response.json()
        
        # Add the folders from this page to our list
        folders_on_page = data['data']
        all_folders.extend(folders_on_page)
        
        logger.info(f"Fetched page {page} with {len(folders_on_page)} folders")
        
        # Check if there are more pages
        if 'next' in data['paging'] and data['paging']['next']:
            page += 1
        else:
            more_pages = False
    
    logger.info(f"Found {len(all_folders)} folders in total")
    return all_folders

def extract_book_name(video_title):
    """Extract the Bible book name from the video title."""
    # Regex to match Bible book patterns at the beginning of a string
    match = re.match(r'^(\d+\s+[A-Za-z]+|[A-Za-z]+)', video_title)
    
    if match:
        book_name = match.group(1).strip()
        return book_name
    return None

def find_matching_folder(book_name, folders):
    """Find a folder that matches the book name."""
    if not book_name:
        return None
    
    book_name_lower = book_name.lower()
    
    for folder in folders:
        folder_name = folder['name']
        folder_name_lower = folder_name.lower()
        
        # Folder name start with the book name
        if folder_name_lower.startswith(book_name_lower):
            return folder
            
        # Folder starts with the book name followed by a space or bracket
        pattern = rf'^{re.escape(book_name_lower)}(\s|\[|$)'
        if re.search(pattern, folder_name_lower):
            return folder
    
    return None

def get_recent_videos(max_videos=3):
    """Get only the most recent videos"""
    logger.info(f"Fetching {max_videos} most recent videos...")
    
    # Get most recent videos
    # Include parent_folder in the response fields
    response = client.get('/me/videos', params={
        'per_page': max_videos, 
        'sort': 'date', 
        'fields': 'uri,name,parent_folder'
    })
    videos = response.json()['data']
    
    logger.info(f"Retrieved {len(videos)} most recent videos")
    return videos

def move_videos_to_folders():
    """Move only the 3 most recent videos to matching folders if parent_folder is NULL."""
    logger.info("\n=== STARTING VIDEO ORGANIZATION ===\n")
    
    # Get all folders using pagination
    folders = get_all_folders()
    
    # Get 3 most recent videos
    videos_to_process = get_recent_videos(max_videos=3)
    
    logger.info(f"\nProcessing {len(videos_to_process)} most recent videos...")
    processed_count = 0
    skipped_count = 0
    already_in_folder_count = 0
    
    for i, video in enumerate(videos_to_process):
        video_id = video['uri'].split('/')[-1]
        video_title = video['name']
        
        logger.info(f"\nProcessing video {i+1}/{len(videos_to_process)}: '{video_title}'")
        logger.debug(f"  Video data: {json.dumps(video, indent=2)}")
        
        # Check if video is already in a folder (parent_folder is not NULL)
        if 'parent_folder' in video and video['parent_folder'] is not None:
            folder_name = video['parent_folder'].get('name', 'Unknown folder')
            logger.info(f"  Already in folder: '{folder_name}'")
            already_in_folder_count += 1
            continue
        
        # Extract book name from the video title
        book_name = extract_book_name(video_title)
        
        if book_name:
            logger.info(f"  Detected book name: '{book_name}'")
            
            # Find a matching folder for this book name
            matching_folder = find_matching_folder(book_name, folders)
            
            if matching_folder:
                folder_id = matching_folder['uri'].split('/')[-1]
                folder_name = matching_folder['name']
                
                logger.info(f"  Moving to folder: '{folder_name}'")
                logger.debug(f"  Folder URI: {matching_folder['uri']}")
                logger.debug(f"  Folder ID: {folder_id}")
                logger.debug(f"  Video URI: {video['uri']}")
                logger.debug(f"  Video ID: {video_id}")
                
                # Move the video to the folder - using the full endpoint
                try:
                    endpoint = f'/me/projects/{folder_id}/videos/{video_id}'
                    logger.debug(f"  Using endpoint: {endpoint}")
                    
                    # Add empty JSON data as per API requirements
                    response = client.put(endpoint, data={})
                    logger.debug(f"  Response status: {response.status_code}")
                    logger.debug(f"  Response body: {response.text}")
                    
                    if response.status_code >= 200 and response.status_code < 300:
                        logger.info(f"  ✓ Successfully moved")
                        processed_count += 1
                    else:
                        logger.error(f"  ✗ Failed with status code: {response.status_code}")
                        skipped_count += 1
                except Exception as e:
                    logger.error(f"  ✗ Error moving video: {str(e)}")
                    skipped_count += 1
            else:
                logger.warning(f"  No matching folder found for '{book_name}'")
                skipped_count += 1
        else:
            logger.warning(f"  No book name detected in title")
            skipped_count += 1


if __name__ == "__main__":
    move_videos_to_folders()