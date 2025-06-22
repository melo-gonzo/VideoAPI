"""Frame deduplication algorithm."""

from typing import Dict, Any, Optional
import numpy as np
from collections import deque

from .base_algorithm import BaseAlgorithm
from ..utils.frame_utils import compute_frame_hash, frames_are_identical
from ..utils.logging_config import get_logger

logger = get_logger("deduplicator")


class FrameDeduplicator(BaseAlgorithm):
    """Algorithm for detecting and filtering duplicate frames."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize frame deduplicator.

        Args:
            config: Configuration with keys:
                - method: 'hash' or 'similarity' (default: 'similarity')
                - threshold: Similarity threshold for 'similarity' method (default: 0.95)
                - hash_method: Hash algorithm for 'hash' method (default: 'md5')
                - history_size: Number of recent frames to compare against (default: 5)
        """
        default_config = {
            "method": "similarity",
            "threshold": 0.95,
            "hash_method": "md5",
            "history_size": 5,
        }

        if config:
            default_config.update(config)

        super().__init__("frame_deduplicator", default_config)

    def _setup(self) -> None:
        """Setup deduplicator state."""
        self.frame_history = deque(maxlen=self.config["history_size"])
        self.hash_history = deque(maxlen=self.config["history_size"])
        self.duplicate_count = 0
        self.total_frames = 0

    def process(self, frame: np.ndarray, frame_info: Dict[str, Any]) -> Dict[str, Any]:
        """Process frame for deduplication.

        Args:
            frame: Input frame
            frame_info: Frame metadata

        Returns:
            Dictionary with keys:
                - is_duplicate: Boolean indicating if frame is duplicate
                - duplicate_count: Number of duplicates detected so far
                - total_frames: Total frames processed
                - duplicate_ratio: Ratio of duplicates to total frames
        """
        if not self.enabled:
            return {
                "is_duplicate": False,
                "duplicate_count": self.duplicate_count,
                "total_frames": self.total_frames,
                "duplicate_ratio": 0.0,
            }

        self.total_frames += 1
        is_duplicate = False

        try:
            if self.config["method"] == "hash":
                is_duplicate = self._check_hash_duplicate(frame)
            elif self.config["method"] == "similarity":
                is_duplicate = self._check_similarity_duplicate(frame)
            else:
                logger.warning(f"Unknown deduplication method: {self.config['method']}")
                return self._get_result(False)

            if is_duplicate:
                self.duplicate_count += 1
                logger.debug(
                    f"Duplicate frame detected (total: {self.duplicate_count})"
                )
            else:
                # Add frame to history for future comparisons
                self._add_to_history(frame)

        except Exception as e:
            logger.error(f"Error in frame deduplication: {e}")
            is_duplicate = False

        return self._get_result(is_duplicate)

    def _check_hash_duplicate(self, frame: np.ndarray) -> bool:
        """Check for duplicate using hash comparison."""
        frame_hash = compute_frame_hash(frame, self.config["hash_method"])

        if frame_hash in self.hash_history:
            return True

        self.hash_history.append(frame_hash)
        return False

    def _check_similarity_duplicate(self, frame: np.ndarray) -> bool:
        """Check for duplicate using similarity comparison."""
        for historical_frame in self.frame_history:
            if frames_are_identical(frame, historical_frame, self.config["threshold"]):
                return True

        return False

    def _add_to_history(self, frame: np.ndarray) -> None:
        """Add frame to history."""
        if self.config["method"] == "similarity":
            # Store a copy of the frame for similarity comparison
            self.frame_history.append(frame.copy())
        # Hash history is managed in _check_hash_duplicate

    def _get_result(self, is_duplicate: bool) -> Dict[str, Any]:
        """Get processing result."""
        duplicate_ratio = (
            self.duplicate_count / self.total_frames if self.total_frames > 0 else 0.0
        )

        return {
            "is_duplicate": is_duplicate,
            "duplicate_count": self.duplicate_count,
            "total_frames": self.total_frames,
            "duplicate_ratio": duplicate_ratio,
        }

    def reset_stats(self) -> None:
        """Reset deduplication statistics."""
        self.duplicate_count = 0
        self.total_frames = 0
        self.frame_history.clear()
        self.hash_history.clear()
        logger.info("Frame deduplication statistics reset")

    def get_stats(self) -> Dict[str, Any]:
        """Get current deduplication statistics."""
        return {
            "duplicate_count": self.duplicate_count,
            "total_frames": self.total_frames,
            "duplicate_ratio": self.duplicate_count / self.total_frames
            if self.total_frames > 0
            else 0.0,
            "history_size": len(self.frame_history),
        }
