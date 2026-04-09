"""
Check if latest WordPress post is correct.
This fetches info about the latest WordPress posts from the "bible study" category, makes sure it has a bible book category and has the video study category.
It then tests that the audio file link exists.
"""

import requests
import os
import re
from dotenv import load_dotenv
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import boto3
from botocore.exceptions import ClientError
from logger import get_logger

load_dotenv()

SCRIPT_NAME = "check_mainsite_post"

logger = get_logger(SCRIPT_NAME, __file__)

def log_extra(**kwargs):
    return {"script_name": SCRIPT_NAME, **kwargs}


# WP Login stuff
url = os.getenv("WP_API_URL")
username = os.getenv("WP_API_USER")
password = os.getenv("WP_API_PASSWORD")
headers = {
    "Accept": "*/*",
    "Content-Type": "application/json",
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }

def getPost(url):
    logger.info("Getting post from wordpress api", extra=log_extra())
    response = requests.get(url,headers=headers)
    if response.status_code == 200:
        post = response.json()
        return post
    else:
        logger.error(f"Error: {response.status_code} - {response.reason}",
                     extra=log_extra(event_type="error", error_message=f"{response.status_code} - {response.reason}"))


def checkWPPost():
    logger.debug("checkWPPost", extra=log_extra())

    required_category = 2420  # Video Studies category ID
    bible_categories = [12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32,
    33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 547, 548, 531, 627, 764, 821,
    863, 869, 875, 974, 1947, 1949, 1993, 1994, 1995, 1996, 1997, 1998, 1999, 2000, 2001,
    2002, 2003, 2004, 2005, 2006, 2007, 2009, 2010, 2011, 2012, 2069, 2070, 2071, 2072,
    2073, 2074, 2163, 2170, 2174, 2238, 2243, 2192, 2420, 2513, 2524]


    posts = getPost(os.getenv("WP_API_URL") + "posts?categories=48&per_page=1")
    if not posts:
        logger.error("Failed to retrieve posts from WordPress API",
                     extra=log_extra(event_type="error", error_message="Failed to retrieve posts from WordPress API"))
        return

    latest_post = posts[0]


    # Convert post date to local time
    post_date = datetime.fromisoformat(latest_post['date'].replace('Z', '+00:00'))
    site_timezone = ZoneInfo("US/Pacific")
    post_date_local = post_date.astimezone(site_timezone)
    current_date_local = datetime.now(site_timezone)

    logger.debug(f"Post date (Local): {post_date_local}", extra=log_extra())
    logger.debug(f"Current date (Local): {current_date_local}", extra=log_extra())

    if post_date_local.date() != current_date_local.date():
        logger.error(f"No Audio Study post found for {current_date_local.date()}",
                     extra=log_extra(event_type="error", error_message=f"No Audio Study post found for {current_date_local.date()}"))
        send_email(latest_post, None, None, f"No Audio Study post found for {current_date_local.date()}")
        return None

    is_valid, content_length, last_modified, validation_message = validate_post(latest_post, required_category, bible_categories)

    if is_valid:
        logger.info("Latest post is valid.", extra=log_extra())
        logger.info(f"Valid post found: {post_title}",
                extra=log_extra(event_type="key_event",
                                post_title=post_title,
                                post_categories=post_categories))
        send_email(latest_post, content_length, last_modified)
        return latest_post
    else:
        logger.info("No valid post found.", extra=log_extra())
        send_email(latest_post, content_length, last_modified, validation_message)
        return None

def validate_post(post, required_category, bible_categories):
    logger.info("validate_post", extra=log_extra())

    # Check if the post has the required category
    if required_category not in post['categories']:
        logger.info("Post does not have 'Video Studies' category.", extra=log_extra())
        return False, None, None, "Post does not have 'Video Studies' category."

    # Check if the post has any of the bible categories
    if not any(category_id in bible_categories for category_id in post['categories']):
        logger.info("Post does not have a required Bible book category.", extra=log_extra())
        return False, None, None, "Post does not have a required Bible book category."

    if post['status'] != 'publish':
        logger.info("Post is not published.", extra=log_extra())
        return False, None, None, "Post is not published."

    pattern = re.compile(r'https://media\.northcountrychapel\.com/rafiles/([a-zA-Z0-9-]+)\.mp3')
    content = post['content']['rendered']
    match = pattern.search(content)
    if not match:
        logger.info("Post does not have an audio file link.", extra=log_extra())
        return False, None, None, "Post does not have an audio file link."

    audio_url = match.group(0)
    try:
        new_headers = {
            'Accept': 'audio/mpeg',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
            'Referer': 'https://example.com'  # Replace with the actual referring URL if needed
        }
        response = requests.head(audio_url, headers=new_headers, allow_redirects=True, timeout=5)

        if response.status_code == 200:
            content_length = response.headers.get('Content-Length')
            last_modified = response.headers.get('Last-Modified')
            logger.info(f"Audio file exists at: {audio_url}", extra=log_extra())

            if content_length:
                content_length = int(content_length)  # Convert to an integer
                logger.info(f"Content-Length: {content_length} bytes", extra=log_extra())
            if last_modified:
                logger.info(f"Last-Modified: {last_modified}", extra=log_extra())

        else:
            logger.info(f"Audio file link is invalid. Status code: {response.status_code}", extra=log_extra())
            return False, None, None, "Audio file link is invalid."
    except requests.exceptions.RequestException as e:
        logger.error(f"Error checking audio file link: {e}",
                     extra=log_extra(event_type="error", error_message=str(e)))
        return False, None, None, f"Error checking audio file link: {e}"

    return True, content_length, last_modified, None


def send_email(post, content_length, last_modified, validation_message=None):
    logger.info("send_email", extra=log_extra())

        # Add diagnostic logging
    logger.debug(f"AWS_REGION: {os.environ.get('AWS_REGION', 'NOT SET')}", extra=log_extra())
    logger.debug(f"EMAIL_FROM: {os.environ.get('EMAIL_FROM', 'NOT SET')}", extra=log_extra())
    logger.debug(f"EMAIL_TO: {os.environ.get('EMAIL_TO', 'NOT SET')}", extra=log_extra())
    logger.debug(f"AWS_ACCESS_KEY_ID: {'SET' if os.environ.get('AWS_ACCESS_KEY_ID') else 'NOT SET'}", extra=log_extra())


    if validation_message:
        subject = "WordPress Check script found an issue"
        html_content = f"""
        <html>
            <body>
                <h3>WordPress Post Check - Issue Found</h3>
                <p>The latest post has an issue:</p>
                <p><strong>Issue:</strong> {validation_message}</p>
                <p><strong>Post Title:</strong> {post['title']['rendered']}</p>
                <p><a href="{post['link']}">View Post</a></p>
            </body>
        </html>
        """
    else:
        subject = "WordPress Check script ran successfully"
        html_content = f"""
        <html>
            <body>
                <h3>WordPress Post Check</h3>
                <p>The latest post is valid and contains the following details:</p>
                <p><strong>Post Title:</strong> {post['title']['rendered']}</p>
                <p><strong>Content-Length:</strong> {content_length} bytes</p>
                <p><strong>Last Modified:</strong> {last_modified}</p>
                <p><a href="{post['link']}">View Post</a></p>
            </body>
        </html>
        """

    # Create AWS SES client
    try:
        ses_client = boto3.client(
            'ses',
            region_name=os.environ.get("AWS_REGION"),
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY")
        )

        response = ses_client.send_email(
            Source=os.environ.get("EMAIL_FROM"),
            Destination={
                'ToAddresses': [os.environ.get("EMAIL_TO")]
            },
            Message={
                'Subject': {
                    'Data': subject,
                    'Charset': 'UTF-8'
                },
                'Body': {
                    'Html': {
                        'Data': html_content,
                        'Charset': 'UTF-8'
                    }
                }
            }
        )

        logger.info(f"Email sent successfully. Message ID: {response['MessageId']}", extra=log_extra())

    except ClientError as e:
        logger.error(f"Error sending email via SES: {e.response['Error']['Message']}",
                     extra=log_extra(event_type="error", error_message=e.response['Error']['Message']))
    except Exception as e:
        logger.error(f"Error sending email: {e}",
                     extra=log_extra(event_type="error", error_message=str(e)))


logger.info(f"Starting script: {SCRIPT_NAME}",
            extra=log_extra(event_type="script_start"))

try:
    checkWPPost()

    logger.info(f"Finished script: {SCRIPT_NAME}",
                extra=log_extra(event_type="script_stop", exit_status="success"))

except Exception as e:
    logger.error(f"Script crashed: {e}",
                 extra=log_extra(event_type="script_stop", exit_status="error",
                                 error_message=str(e)))