"""VideoAPI - A lightweight video streaming and recording library."""

__version__ = "0.1.0"

from videoapi.core.video_stream import VideoStream
from videoapi.core.video_recorder import VideoRecorder
from videoapi.core.frame_processor import FrameProcessor
from videoapi.core.playback_manager import PlaybackManager
from videoapi.core.config_manager import ConfigManager

__all__ = [
    "VideoStream",
    "VideoRecorder",
    "FrameProcessor",
    "PlaybackManager",
    "ConfigManager",
]
