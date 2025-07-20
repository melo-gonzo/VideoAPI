"""Time-related utilities."""

from datetime import datetime


def nicetime() -> str:
    """Get current time formatted for filenames."""
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human readable string."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"
