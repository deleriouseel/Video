import vimeo
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict
from ..models.data_models import VimeoVideo
from ..config.settings import config
from ..utils.logging import get_logger
from ..utils.retry import exponential_backoff, RetryConfig 

logger = get_logger()

class VimeoService:
    def __init__(self):
        self.client = vimeo.VimeoClient(
            token=config.vimeo.token,
            key=config.vimeo.key,
            secret=config.vimeo.secret,
        )

        self.retry_config = RetryConfig(
            max_attempts=3,
            base_delay=2.0,
            max_delay=30.0
        )
    @exponential_backoff(retry_exceptions=(Exception,))

    def get_recent_videos(self, count: int = 3) -> List[VimeoVideo]:
        """Get recent videos from Vimeo"""
        try:
            response = self.client.get(
                f'/users/{config.vimeo.user_id}/videos',
                params={
                    "sort": "date",
                    "direction": "desc",
                    'per_page': count
                    }
                    
            ).json()
            
            videos = []

            for video_data in response.get("data", []):
                video = VimeoVideo(
                    id= video_data["uri"].split("/")[-1],
                    title=video_data["name"],
                    uri=video_data["uri"],
                    date=datetime.strptime(video_data["created_time"], "%Y-%m-%dT%H:%M:%SZ")
                    )
                videos.append(video)
                logger.debug(f"Found video: {video.title} ({video.id})")
            return videos
        except Exception as e:
            logger.error(f"Failed to get Vimeo videos: {e}")
            raise
    
    @exponential_backoff(retry_exceptions=(Exception,))
    def upload_video(
        self,
        file_path: Path,
        title: Optional[str] = None,
    ) -> Optional[str]:
        """Upload a video to Vimeo"""
        try:
            logger.info(f"Starting upload of {file_path.name}")

            metadata = {
                "name": title or file_path.stem,
                "privacy": {
                    "view": "anybody"
                },
                "content_rating": "safe",
                "license": "by-nc-sa",
                "tags": config.video.default_tags,
                }
            
            # Upload the video
            uri = self.client.upload(
                str(file_path),
                data=metadata
            )

            video_id = uri.split("/")[-1]
            logger.info(f"Successfully uploaded {file_path.name} with ID {video_id}")
            return video_id
        
        except Exception as e:
            logger.error(f"Failed to upload video {file_path.name}: {e}")
            raise

    @exponential_backoff(retry_exceptions=(Exception,))
    def update_video_title(self, video_id: str, new_title: str) -> bool:
        """Update the title of a Vimeo video"""
        try:
            self.client.patch(
                f'/videos/{video_id}',
                data={"name": new_title}
            )
            logger.info(f"Successfully updated title for video {video_id}: {new_title}")
            return True
        except Exception as e:
            logger.error(f"Failed to update title for video {video_id}: {e}")
            raise
