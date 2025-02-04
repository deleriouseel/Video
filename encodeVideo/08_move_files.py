'''
Move video files to the backup server if it is at least 4 days old.
'''

import os
import shutil
import time
from datetime import datetime, timedelta
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    filename=r"C:\Users\AudioVisual\Documents\GitHub\Video\filename.log",
)

source_dir = r"D:\Studies"
network_dir = r"\\DocuSynology\video"

logging.info("Starting move_files.py")

now = time.time()

# Fles older than 4 days
cutoff_time = now - (4 * 24 * 60 * 60)
logging.debug(datetime.fromtimestamp(cutoff_time))

# Loop through all files in the local directory
for filename in os.listdir(source_dir):
    file_path = os.path.join(source_dir, filename)
    logging.debug(file_path)

    
    if os.path.isfile(file_path):
        file_modified_time = os.path.getmtime(file_path)
        #If file is > 4 days old
        if file_modified_time > cutoff_time:
            # Get the folder name
            target_folder = filename[:6]
            logging.debug(target_folder)
            target_path = os.path.join(source_dir, target_folder)
            network_target_path = os.path.join(network_dir, target_folder)

            # Create the target folder if it doesn't exist
            os.makedirs(target_path, exist_ok=True)
            os.makedirs(network_target_path, exist_ok=True)
                        
            # Copy the file to the backup folder
            logging.info(f"Copying {filename} to {network_target_path}")
            network_target_file_path = os.path.join(network_target_path, filename)
            shutil.copy2(file_path, network_target_file_path)
            logging.info(f"Finished copying {filename}")

            # Move to local folder
            logging.info(f"Moving {filename} to {target_path}")
            shutil.move(file_path, os.path.join(target_path, filename))
            logging.info(f"Finished moving {filename}")