from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

@dataclass
class VideoFile:
    path: Path
    creation_date: datetime
    duration: Optional[float] = None
    encoded_path: Optional[Path] = None

    @property
    def filename(self) -> str:
        return self.path.name
    
    @property
    def duration_minutes(self) -> float:
        return (self.duration or 0) / 60
    
@dataclass
class WordpressPost:
    id: int
    title: str
    date: datetime
    content: str
    filename: Optional[str] = None
    
    
@dataclass
class VimeoVideo:
    id: int
    title: str
    uri: str
    date: datetime
    size: Optional[float] = None

    @property
    def size_gb(self) -> float:
        return (self.size or 0) / (1024 ** 3)
    
@dataclass
class EmbedPair:
    post_id: int
    post_title: str
    post_date: datetime
    video_id: str
    video_title: str
    video_date: datetime
    similarity_score: float
    embed_code: Optional[str] = None