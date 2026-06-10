import os
import datetime
import json
import vimeo
from dotenv import load_dotenv
from logger import get_logger

# Load environment variables
load_dotenv()

today = str(datetime.date.today())
SCRIPT_NAME = "vimeo_m3u8"

logger = get_logger(SCRIPT_NAME, __file__)

def log_extra(**kwargs):
    return {"script_name": SCRIPT_NAME, **kwargs}


def get_m3u8_links():
    """
    Get the m3u8 links for the latest videos and save them to text file
    """
    client = vimeo.VimeoClient(
        token=os.getenv('VIMEO_TOKEN'),
        key=os.getenv("VIMEO_KEY"),
        secret=os.getenv("VIMEO_SECRET"),
    )
    logger.info("Getting latest videos from Vimeo", extra=log_extra())

    # Create a list to store all the links and information
    all_links = []

    try:
        # Get the latest videos (default: 3)
        response = client.get(f'/users/75458348/videos', params={
            'sort': 'date',
            'direction': 'desc',
            'per_page': 3
        })

        # Parse the response
        videos_data = response.json()
        logger.debug(f"Vimeo API response status: {response.status_code}, videos returned: {len(videos_data.get('data', []))}",
                     extra=log_extra())

        # Process each video
        for video in videos_data['data']:
            video_id = video["uri"].split('/')[-1]
            video_title = video["name"]

            logger.info(f"Processing video: {video_title} (ID: {video_id})",
                        extra=log_extra(video_id=video_id))

            # Find the m3u8 link in the files array
            m3u8_link = None

            for file_info in video["files"]:
                if file_info.get("quality") == "hls" and "link" in file_info:
                    # Get the original m3u8 link
                    original_link = file_info["link"]

                    # Replace oauth2_token_id parameter with logging=false
                    if "oauth2_token_id=" in original_link:
                        m3u8_link = original_link.split("oauth2_token_id=")[0] + "logging=false"
                    else:
                        m3u8_link = original_link

                    logger.debug(f"Original m3u8 link: {original_link}",
                                 extra=log_extra(video_id=video_id))
                    logger.debug(f"Modified m3u8 link: {m3u8_link}",
                                 extra=log_extra(video_id=video_id))
                    break

            if m3u8_link:
                logger.info(f"Found m3u8 link for '{video_title}' (ID: {video_id}): {m3u8_link}",
                            extra=log_extra(event_type="key_event", video_title=video_title, m3u8_link=m3u8_link))
                # Add the video info and link to our list
                all_links.append({
                    "video_id": video_id,
                    "title": video_title,
                    "link": m3u8_link
                })
            else:
                logger.warning(f"No m3u8 link found for video: {video_title}",
                               extra=log_extra(event_type="error", error_message=f"No m3u8 link found for video: {video_title}", video_id=video_id))

        logger.info(f"Extracted {len(all_links)} m3u8 links",
                    extra=log_extra(event_type="key_event",
                                    extraction_status="success",
                                    file_count=len(all_links)))
        # Save all links to a single file
        if all_links:
            save_links_to_file(all_links)

    except Exception as e:
        logger.error(f"Error getting videos: {e}",
                     extra=log_extra(event_type="error", error_message=str(e)))
        return None


def save_links_to_file(links_data):
    """
    Save all m3u8 links to the desktop
    """
    try:
        # Get desktop path
        desktop_path = "C:\\Users\\KristinHoppe\\Desktop"
        file_path = os.path.join(desktop_path, f"vimeo_m3u8_links_{today}.txt")

        with open(file_path, 'w') as f:
            for item in links_data:
                f.write(f"# {item['title']} (ID: {item['video_id']})\n")
                f.write(f"{item['link']}\n\n")

        if os.path.exists(file_path):
            logger.debug(f"Verified file exists at {file_path}, size: {os.path.getsize(file_path)} bytes",
                         extra=log_extra())
        else:
            logger.warning(f"File NOT found at {file_path} after write attempt",
                           extra=log_extra(event_type="error", error_message=f"File NOT found at {file_path} after write attempt"))

        logger.info(f"Saved all m3u8 links to {file_path}",
                    extra=log_extra(file_path=file_path, link_count=len(links_data)))
        return file_path
    except Exception as e:
        logger.error(f"Error saving links to file: {e}",
                     extra=log_extra(event_type="error", error_message=str(e)))
        return None


if __name__ == "__main__":
    logger.info(f"Starting script: {SCRIPT_NAME}",
                extra=log_extra(event_type="script_start"))

    try:
        get_m3u8_links()

        logger.info(f"Finished script: {SCRIPT_NAME}",
                    extra=log_extra(event_type="script_stop", exit_status="success"))

    except Exception as e:
        logger.error(f"Script crashed: {e}",
                     extra=log_extra(event_type="script_stop", exit_status="error",
                                     error_message=str(e)))