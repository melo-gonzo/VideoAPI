"""VideoAPI utilities package."""

from videoapi.utils.logging_config import setup_logging, get_logger
from videoapi.utils.time_utils import nicetime, format_duration
from videoapi.utils.frame_utils import (
    resize_frame,
    compute_frame_hash,
    frames_are_identical,
)

__all__ = [
    "setup_logging",
    "get_logger",
    "nicetime",
    "format_duration",
    "resize_frame",
    "compute_frame_hash",
    "frames_are_identical",
]
