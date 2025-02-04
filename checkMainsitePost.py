"""
Check if latest WordPress post is correct.
This fetches info about the latest WordPress posts from the "bible study" category, makes sure it has a bible book category and has the video study category.
It then tests that the audio file link exists.
"""

import logging
import requests
import os
import datetime
import re
from dotenv import load_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

load_dotenv()
today = str(datetime.date.today())

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    filename=r"WPpost.log",
)
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
    logging.info("Getting post from wordpress api")
    response = requests.get(url,headers=headers)
    if response.status_code == 200:
        post = response.json()
        return post
    else:
        logging.error(f"Error: {response.status_code} - {response.reason}")   


def checkWPPost():
    logging.info("checkWPPost")
    
    required_category = 2420  # Video Studies category ID
    bible_categories = [12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 
    33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 547, 548, 531, 627, 764, 821, 
    863, 869, 875, 974, 1947, 1949, 1993, 1994, 1995, 1996, 1997, 1998, 1999, 2000, 2001, 
    2002, 2003, 2004, 2005, 2006, 2007, 2009, 2010, 2011, 2012, 2069, 2070, 2071, 2072, 
    2073, 2074, 2163, 2170, 2174, 2238, 2243, 2192, 2420, 2513, 2524]


    posts = getPost(os.getenv("WP_API_URL") + "posts?categories=48&per_page=1")
    if not posts:
        logging.error("Failed to retrieve posts from WordPress API")
        return
    
    latest_post = posts[0]

    from datetime import datetime, timezone
    post_date = datetime.fromisoformat(latest_post['date'].replace('Z', '+00:00'))
    current_date = datetime.now(timezone.utc)


    if post_date.date() != current_date.date():
        logging.error(f"No Audio Study post found for {current_date.date()}")
        send_email(latest_post, None, None, f"No Audio Study post found for {current_date.date()}")
        return None

    is_valid, content_length, last_modified, validation_message = validate_post(latest_post, required_category, bible_categories)

    if is_valid:
        logging.info("Latest post is valid.")
        send_email(latest_post, content_length, last_modified)
        return latest_post
    else:
        logging.info("No valid post found.")
        send_email(latest_post, content_length, last_modified, validation_message)
        return None
    
    
def validate_post(post, required_category, bible_categories):
    logging.info("validate_post")
    
    # Check if the post has the required category
    if required_category not in post['categories']:
        logging.info("Post does not have 'Video Studies' category.")
        return False, None, None, "Post does not have 'Video Studies' category."
    
    # Check if the post has any of the bible categories
    if not any(category_id in bible_categories for category_id in post['categories']):
        logging.info("Post does not have a required Bible book category.")
        return False, None, None, "Post does not have a required Bible book category."
    
    if post['status'] != 'publish':
        logging.info("Post is not published.")
        return False, None, None, "Post is not published."
    
    pattern = re.compile(r'https://media\.northcountrychapel\.com/rafiles/([a-zA-Z0-9-]+)\.mp3')
    content = post['content']['rendered']
    match = pattern.search(content)
    if not match:
        logging.info("Post does not have an audio file link.")
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
            logging.info(f"Audio file exists at: {audio_url}")
            
            if content_length:
                content_length = int(content_length)  # Convert to an integer
                logging.info(f"Content-Length: {content_length} bytes")
            if last_modified:
                logging.info(f"Last-Modified: {last_modified}")
            
        else:
            logging.info(f"Audio file link is invalid. Status code: {response.status_code}")
            return False, None, None, "Audio file link is invalid."
    except requests.exceptions.RequestException as e:
        logging.error(f"Error checking audio file link: {e}")
        return False, None, None, f"Error checking audio file link: {e}"
    
    return True, content_length, last_modified, None

def send_email(post, content_length, last_modified, validation_message=None):
    logging.info("send_email")
    
    if validation_message:
        subject = "WordPress check script found an issue"
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
        subject = "WordPress check script ran successfully"
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

    message = Mail(
        from_email=os.environ.get("EMAIL_FROM"),
        to_emails=os.environ.get("EMAIL_TO"),
        subject=subject,
        html_content=html_content,
    )

    try:
        sg = SendGridAPIClient(os.environ.get("SENDGRID_API_KEY"))
        response = sg.send(message)
        logging.info(f"Email sent with status code: {response.status_code}")
    except Exception as e:
        logging.error(f"Error sending email: {e}")

checkWPPost()