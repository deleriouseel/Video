from dataclasses import dataclass, field
from pathlib import Path
from typing import List
import os
from dotenv import load_dotenv
from ..utils.logging import get_logger

load_dotenv()
logger = get_logger()

@dataclass
class WordPressConfig:
    api_url: str = os.getenv("WP_API_URL", "")
    username: str = os.getenv("WP_API_USER", "")
    password: str = os.getenv("WP_API_PASSWORD", "")
    category_id: int = 48 # Audio Studies category
    posts_per_page: int = 3

@dataclass
class VimeoConfig:
    token: str = os.getenv("VIMEO_TOKEN", "")
    key: str = os.getenv("VIMEO_KEY", "")
    secret: str = os.getenv("VIMEO_SECRET", "")
    user_id: str = os.getenv("VIMEO_USER_ID", "")

@dataclass
class PathConfig:
    desktop_path: Path = Path.home() / "Desktop"
    studies_path: Path = Path("D:/Studies")
    log_path: Path = Path("C:/Users/AudioVisual/Documents/GitHub/Video/filename.log")

@dataclass
class VideoConfig:
    min_size_gb: float = 1.5
    max_size_gb: float = 6.0
    min_duration_minutes: float = 30.0
    default_tags: List[str] = field(default_factory=lambda: ["northcountrychapel", "ncc", "bible study"])

@dataclass
class AppConfig:
    wordpress: WordPressConfig = field(default_factory=WordPressConfig)
    vimeo: VimeoConfig = field(default_factory=VimeoConfig)
    paths: PathConfig = field(default_factory=PathConfig)
    video: VideoConfig = field(default_factory=VideoConfig)

    def validate(self) -> List[str]:
        """Validate configuration settings."""
        errors = []
        # Wordpress validation
        if not self.wordpress.api_url:
            logger.error("WordPress API URL is not set.")
            errors.append("WordPress API URL is not set.")
        if not self.wordpress.username:
            logger.error("WordPress username is not set.")
            errors.append("WordPress username is not set.")
        if not self.wordpress.password:
            logger.error("WordPress password is not set.")
            errors.append("WordPress password is not set.")
        # Vimeo validation
        if not self.vimeo.token:
            logger.error("Vimeo token is not set.")
            errors.append("Vimeo token is not set.")
        if not self.vimeo.key:
            logger.error("Vimeo key is not set.")
            errors.append("Vimeo key is not set.")
        if not self.vimeo.secret:
            logger.error("Vimeo secret is not set.")
            errors.append("Vimeo secret is not set.")
        if not self.vimeo.user_id:
            logger.error("Vimeo user ID is not set.")
            errors.append("Vimeo user ID is not set.")
        # Path validation
        if not self.paths.studies_path.exists():
            logger.error(f"Studies path does not exist: {self.paths.studies_path}")
            errors.append(f"Studies path does not exist: {self.paths.studies_path}")
        
        if errors:
            logger.error(f"Configuration errors: {errors}")
        else:
            logger.info("Configuration validated successfully.")
        
        return errors

    
# Create global config instance
config = AppConfig()