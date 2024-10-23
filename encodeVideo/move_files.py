import os
import shutil
import time
from datetime import datetime, timedelta
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    filename="filename.log",
)

# Set the directory to scan
source_dir = r"D:\Studies"
network_dir = r"\\DocuSynology\video"


# Get the current time
now = time.time()

# Fles older than 4 days
cutoff_time = now - (4 * 24 * 60 * 60)

# Loop through all files in the source directory
for filename in os.listdir(source_dir):
    file_path = os.path.join(source_dir, filename)
    logging.debug(file_path)

    
    if os.path.isfile(file_path):
        file_modified_time = os.path.getmtime(file_path)

        if file_modified_time < cutoff_time:
            # Extract the first 6 characters of the filename
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
            #Move to local folder
            logging.info(f"Moving {filename} to {target_path}")
            shutil.move(file_path, os.path.join(target_path, filename))
            logging.info(f"Finished moving {filename}")



print("File moving process completed.")
