'''
If .MOV files on the desktop were created on the previous Friday, Sunday, or Monday:
Normalize audio and encode video files on desktop using FFmpeg equivalent of Handbrake Fast 1080p30 -crf 21. Saves to D:\Studies. 

'''

import subprocess
import os
import glob
import logging
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    filename=r"C:\Users\AudioVisual\Documents\GitHub\Video\filename.log",
)

desktop = os.path.join(os.path.expanduser("~"), "Desktop")

def get_latest_days():
    # Get today's date
    today = datetime.today()

    # Calculate the last Friday
    days_since_friday = (today.weekday() - 4 + 7) % 7
    latest_friday = today - timedelta(days=days_since_friday)
    
    # Calculate the last Sunday
    days_since_sunday = (today.weekday() - 6 + 7) % 7
    latest_sunday = today - timedelta(days=days_since_sunday)
    
    # Calculate the last Monday
    days_since_monday = (today.weekday() - 0 + 7) % 7
    latest_monday = today - timedelta(days=days_since_monday)

    logging.info(f"Latest Friday: {latest_friday.date()}")
    logging.info(f"Latest Sunday: {latest_sunday.date()}")
    logging.info(f"Latest Monday: {latest_monday.date()}")

    return latest_friday.date(), latest_sunday.date(), latest_monday.date()

def get_peak_volume(input_file):
    # FFmpeg command to get the max volume
    command = [
        'ffmpeg', '-i', input_file,
        '-af', 'volumedetect',
        '-vn', '-sn', '-dn',
        '-f', 'null', '/dev/null'
    ]
    
    # Run the command and capture output
    result = subprocess.run(command, stderr=subprocess.PIPE, text=True)
    
    # Find the max_volume from the output
    for line in result.stderr.splitlines():
        if 'max_volume' in line:
            peak_volume = float(line.split()[4].replace('dB', ''))
            return peak_volume
    
    # If no peak volume is found, return 0 
    return 0

def convert_video(input_file, output_file):
    logging.debug(f"Convert video function: {input_file}, {output_file}")

    peak_volume = get_peak_volume(input_file)
    gain = -peak_volume  # Normalize to 0 dB
    logging.debug(f"Peak volume: {peak_volume}")
    logging.info(f"Gain applied: {gain}")

    # FFmpeg command
    command = [
        'ffmpeg',
        '-y',
        '-i', input_file,
        '-vf', 'yadif,scale=1920:1080', 
        '-r', '30',
        '-c:v', 'libx264',
        '-crf', '21',
        '-preset', 'medium',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-af', f'volume={gain}dB,loudnorm',
        output_file
    ]
    # Execute the FFmpeg command
    try:
        subprocess.run(command, check=True)
        print(f"Conversion successful: {output_file}")
    except subprocess.CalledProcessError as e:
        print(f"An error occurred during conversion: {e}")

def process_files(directory):

    latest_friday, latest_sunday, latest_monday = get_latest_days()

    search_pattern = os.path.join(directory, '*.MOV')
    
    # Find all .MOV files
    MOV_files = glob.glob(search_pattern)
    logging.debug(MOV_files)
    
    if not MOV_files:
        logging.error("No .MOV files found on the desktop.")
        return
    output_folder = 'D:\\Studies'
    
    for input_file in MOV_files:

        file_timestamp = os.path.getmtime(input_file)
        file_date = datetime.fromtimestamp(file_timestamp).date()
        logging.debug(file_date)


        if file_date in {latest_friday, latest_sunday, latest_monday}:
            # Define the output file path
            file_name = os.path.basename(input_file)
            output_file = os.path.join(output_folder, file_name.replace('.MOV', '.mp4'))
            logging.debug(f"Processing: {input_file} -> {output_file}")

            # Convert the video
            convert_video(input_file, output_file)
            logging.info(f"Converting: {input_file}")

process_files(desktop)