'''
Deletes files from D:/Studies if they exist on the backup, are at least 3 weeks old, and are .mp4s.
'''
import os
import shutil
import time
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    filename=r"C:\Users\AudioVisual\Documents\GitHub\Video\filename.log",
)

source_dir = r"D:\Studies"
network_dir = r"\\DocuSynology\video"

# Get the current time
now = time.time()

# Calculate files older than 3 weeks
cutoff_time = now - (3 * 7 * 24 * 60 * 60)
logging.info("Starting delete_oldFiles.py")
# Loop through all folders in the source directory
for foldername in os.listdir(source_dir):
    folder_path = os.path.join(source_dir, foldername)

    # Check if it's a directory
    if os.path.isdir(folder_path):
        # Loop through all files in the folder
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)

            # Check if it's a file and .mp4
            if os.path.isfile(file_path) and filename.lower().endswith('.mp4'):
                # Get the last modified time of the file
                file_modified_time = os.path.getmtime(file_path)
                

                # Check if the file is older than 3 weeks
                if file_modified_time < cutoff_time:
                    # Create the network target path
                    network_target_file_path = os.path.join(network_dir, foldername, filename)
                    logging.debug(f"Files found: {network_target_file_path}")

                    # Check if the file exists on the network
                    if os.path.isfile(network_target_file_path):
                        logging.info(f"Exists in backup: {network_target_file_path}")
                        # If it exists, delete the local copy
                        os.remove(file_path)
                        logging.info(f"Deleted local copy: {file_path}")
                    else:
                        # If it doesn't exist, move it to the network folder
                        os.makedirs(os.path.dirname(network_target_file_path), exist_ok=True)
                        shutil.move(file_path, network_target_file_path)
                        logging.info(f"Moved: {file_path} to {network_target_file_path}")
