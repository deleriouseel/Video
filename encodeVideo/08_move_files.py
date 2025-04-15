'''
Move video files to the backup server if it is at least 4 days old.
First moves files to local bookname folder, then attempts to copy to remote folder.
'''
import os
import shutil
import time
from datetime import datetime, timedelta
import logging
import traceback

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    filename=r"C:\Users\AudioVisual\Documents\GitHub\Video\filename.log",
)
source_dir = r"D:\Studies"
network_dir = r"\\DocuSynology\video"

try:
    # Test if network path exists and is accessible
    if not os.path.exists(network_dir):
        logging.error(f"Network directory {network_dir} does not exist or is not accessible")
    else:
        logging.info(f"Network directory {network_dir} is accessible")
except Exception as e:
    logging.error(f"Error checking network directory: {str(e)}")


logging.info("Starting move_files.py")
now = time.time()
# Files older than 4 days
cutoff_time = now - (4 * 24 * 60 * 60)
logging.debug(f"Cutoff date: {datetime.fromtimestamp(cutoff_time)}")

# Loop through all files in the local directory
for filename in os.listdir(source_dir):
    file_path = os.path.join(source_dir, filename)
    #logging.debug(f"Processing: {file_path}")
    # After setting file_path, add:
    if os.path.isdir(file_path):
        logging.debug(f"Skipping directory: {file_path}")
    elif os.path.isfile(file_path):
        logging.debug(f"Processing file: {file_path}")
    else:
        logging.debug(f"Unknown item type: {file_path}")
   
    if os.path.isfile(file_path):
        file_modified_time = os.path.getmtime(file_path)
        # After checking file_modified_time, add this:
        logging.debug(f"File {filename} modified on: {datetime.fromtimestamp(file_modified_time)}")
        logging.debug(f"Is it older than cutoff? {file_modified_time < cutoff_time}")
        # If file is > 4 days old
        if file_modified_time < cutoff_time:  # Changed > to < to correctly identify older files
            # Get the folder name
            target_folder = filename[:6]
            logging.debug(f"Target folder: {target_folder}")
            
            # Setup local target path
            target_path = os.path.join(source_dir, target_folder)
            # Create the local target folder if it doesn't exist
            os.makedirs(target_path, exist_ok=True)
            
            # First move file to local folder
            local_target_file = os.path.join(target_path, filename)
            logging.info(f"Moving {filename} to local folder {target_path}")
            shutil.move(file_path, local_target_file)
            logging.info(f"Finished moving {filename} to local folder")
            
            # Then try to copy to network location
            try:
                network_target_path = os.path.join(network_dir, target_folder)
                # Create the network target folder if it doesn't exist
                os.makedirs(network_target_path, exist_ok=True)
                
                # Copy the file to the network folder
                network_target_file_path = os.path.join(network_target_path, filename)
                logging.info(f"Copying {filename} to network folder {network_target_path}")
                shutil.copy2(local_target_file, network_target_file_path)
                logging.info(f"Finished copying {filename} to network folder")
            except Exception as e:
                # Log the full exception details including traceback
                logging.error(f"Failed to copy {filename} to network: {str(e)}")
                logging.error(f"Exception details: {traceback.format_exc()}")
                logging.info(f"File was moved to local folder, will try network copy later")