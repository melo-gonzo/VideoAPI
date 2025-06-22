"""Frame processing utilities."""

import cv2
import numpy as np
import hashlib


def resize_frame(frame: np.ndarray, width: int, height: int) -> np.ndarray:
    """Resize frame to specified dimensions."""
    return cv2.resize(frame, (width, height))


def compute_frame_hash(frame: np.ndarray, method: str = "md5") -> str:
    """Compute hash of frame for deduplication.

    Args:
        frame: Input frame
        method: Hash method ('md5', 'sha1', 'sha256')

    Returns:
        Hexadecimal hash string
    """
    # Convert frame to bytes
    frame_bytes = frame.tobytes()

    if method == "md5":
        return hashlib.md5(frame_bytes).hexdigest()
    elif method == "sha1":
        return hashlib.sha1(frame_bytes).hexdigest()
    elif method == "sha256":
        return hashlib.sha256(frame_bytes).hexdigest()
    else:
        raise ValueError(f"Unsupported hash method: {method}")


def frames_are_identical(
    frame1: np.ndarray, frame2: np.ndarray, threshold: float = 0.95
) -> bool:
    """Check if two frames are identical using structural similarity.

    Args:
        frame1: First frame
        frame2: Second frame
        threshold: Similarity threshold (0.0 to 1.0)

    Returns:
        True if frames are considered identical
    """
    if frame1.shape != frame2.shape:
        return False

    # Convert to grayscale for comparison
    gray1 = (
        cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY) if len(frame1.shape) == 3 else frame1
    )
    gray2 = (
        cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY) if len(frame2.shape) == 3 else frame2
    )

    # Calculate structural similarity
    similarity = cv2.matchTemplate(gray1, gray2, cv2.TM_CCOEFF_NORMED)[0][0]

    return similarity >= threshold
