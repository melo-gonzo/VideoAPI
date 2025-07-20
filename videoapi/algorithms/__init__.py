"""VideoAPI algorithms package."""

from videoapi.algorithms.base_algorithm import BaseAlgorithm
from videoapi.algorithms.frame_deduplicator import FrameDeduplicator

__all__ = [
    "BaseAlgorithm",
    "FrameDeduplicator",
]
