import subprocess
import os
import glob
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    filename="filename.log",
)

desktop = os.path.join(os.path.expanduser("~"), "Desktop")

def convert_video(input_file, output_file):
    logging.debug(f"Convert video function: {input_file}, {output_file}")

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
        '-filter:a','loudnorm',
        output_file
    ]
    # Execute the FFmpeg command
    try:
        subprocess.run(command, check=True)
        print(f"Conversion successful: {output_file}")
    except subprocess.CalledProcessError as e:
        print(f"An error occurred during conversion: {e}")

def process_files(directory):
    search_pattern = os.path.join(directory, '*.MOV')
    
    # Find all .MOV files
    MOV_files = glob.glob(search_pattern)
    logging.debug(MOV_files)
    
    if not MOV_files:
        logging.error("No .MOV filewhats found on the desktop.")
        return
    output_folder = 'D:\\Studies'
    
    for input_file in MOV_files:
        # Define the output file path
        file_name = os.path.basename(input_file)
        output_file = os.path.join(output_folder, file_name.replace('.MOV', '.mp4'))
        logging.debug(output_file)
        
        # Convert the video
        convert_video(input_file, output_file)
        logging.info(f"Converting: {input_file}")

process_files(desktop)