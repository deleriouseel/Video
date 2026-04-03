import requests
import logging
import re
from datetime import datetime
from typing import List, Optional
from ..models.data_models import WordpressPost
from ..config.settings import config
from ..utils.logging import get_logger
from ..utils.retry import exponential_backoff, RetryConfig

logger = get_logger()

class WordPressClient:
    def __init__(self):
        self.api_url = config.wordpress.api_url
        self.auth = (config.wordpress.username, config.wordpress.password)
        self.headers = {
            "Accept": "*/*",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
        }

        self.retry_config = RetryConfig(
            max_attempts=3,
            base_delay=2.0,
            max_delay=30.0
        )
    
    def _extract_filename(self, content: str) -> Optional[str]:
        """Extract the filename from post content"""

        pattern = re.compile(
            r'https://media\.northcountrychapel\.com/rafiles/([a-zA-Z0-9-]+)\.mp3'
        )

        if match := pattern.search(content):
            return match.group(1)
        return None
    
    @exponential_backoff(retry_exceptions=(requests.RequestException,))
    def get_recent_posts(self, count: int = 3) -> List[WordpressPost]:
        """Get recent bible study posts"""
        try:
            url = f"{self.api_url}posts"
            params = {
                "categories": config.wordpress.category_id,
                "per_page": count
            }

            response = requests.get(
                url,
                headers = self.headers,
                params = params,
            )
            response.raise_for_status()

            posts = []

            for post_data in response.json():

                post = WordpressPost(
                    id = post_data["id"],
                    title = post_data["title"]["rendered"],
                    date = datetime.strptime(
                        post_data["date"], 
                        "%Y-%m-%dT%H:%M:%S"
                    ),
                    content = post_data["content"]["rendered"],
                    filename = self._extract_filename(post_data["content"]["rendered"])
                )
                posts.append(post)
                logger.debug(f"Found post: {post.title} with filename {post.filename}")

            return posts
        except requests.RequestException as e:
            logger.error(f"Failed to get Wordpress posts: {e}")
            raise 
        
    @exponential_backoff(retry_exceptions=(requests.RequestException,))
    def update_post(self, post_id: int, content: dict) -> bool:
        """Update a Wordpress post"""
        try:
            url = f"{self.api_url}posts/{post_id}"

            response = requests.put(
                url,
                headers = self.headers,
                auth = self.auth,
                json = content
            )
            response.raise_for_status()

            logger.info(f"Successfully updated post {post_id}")
            return True
        except requests.RequestException as e:
            logger.errror(f"Failed to update post {post_id}: {e}")
            raise

    def update_post_with_video(self, post_id: int, video_id: str, video_title: str) -> bool:
        """Add video embed to a Wordpress post"""
        try:
            # Get the current post content
            url = f"{self.api_url}posts/{post_id}"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()

            current_content = response.json()["content"]["rendered"]

            # Create embed code
            embed_code = (
                f'<div style="padding:56.25% 0 0 0;position:relative;"><iframe src="https://player.vimeo.com/video/{video_id}?badge=0&amp;autopause=0&amp;player_id=0&amp;app_id=58479" frameborder="0" allow="autoplay; fullscreen; picture-in-picture; clipboard-write" style="position:absolute;top:0;left:0;width:100%;height:100%;" title="{video_title}"></iframe></div><script src="https://player.vimeo.com/api/player.js"></script>'
            )

            # Update post with new content
            new_content = current_content + "\n" + embed_code
            return self.update_post(
                post_id,
                {"content": new_content}
            )

        except Exception as e:
            logger.error(f"Failed to update post {post_id} with video {video_id}: {e}")
            return False