"""Base algorithm interface for frame processing."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import numpy as np

from ..utils.logging_config import get_logger

logger = get_logger("algorithms")


class BaseAlgorithm(ABC):
    """Base class for all frame processing algorithms."""

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        """Initialize algorithm.

        Args:
            name: Algorithm name
            config: Algorithm-specific configuration
        """
        self.name = name
        self.config = config or {}
        self.enabled = True
        self._setup()

    def _setup(self) -> None:
        """Setup algorithm-specific initialization."""
        pass

    @abstractmethod
    def process(self, frame: np.ndarray, frame_info: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single frame.

        Args:
            frame: Input frame
            frame_info: Frame metadata (timestamp, counter, etc.)

        Returns:
            Processing results dictionary
        """
        pass

    def enable(self) -> None:
        """Enable algorithm processing."""
        self.enabled = True
        logger.debug(f"Algorithm '{self.name}' enabled")

    def disable(self) -> None:
        """Disable algorithm processing."""
        self.enabled = False
        logger.debug(f"Algorithm '{self.name}' disabled")

    def update_config(self, config: Dict[str, Any]) -> None:
        """Update algorithm configuration.

        Args:
            config: New configuration values
        """
        self.config.update(config)
        logger.debug(f"Algorithm '{self.name}' configuration updated")

    def get_config(self) -> Dict[str, Any]:
        """Get current algorithm configuration."""
        return self.config.copy()

    def cleanup(self) -> None:
        """Cleanup algorithm resources."""
        pass
