"""Configuration management for VideoAPI."""

import yaml
from typing import Dict, Any, Optional, Union
from pathlib import Path

from videoapi.utils.logging_config import get_logger

logger = get_logger("config")


class ConfigManager:
    """Manages configuration loading and validation."""

    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        """Initialize ConfigManager.

        Args:
            config_path: Path to configuration file
        """
        self.config_path = config_path
        self.config = {}
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from file."""
        if self.config_path is None:
            self.config = self._get_default_config()
            logger.info("Using default configuration")
            return

        try:
            with open(self.config_path, "r") as file:
                self.config = yaml.safe_load(file)
            logger.info(f"Loaded configuration from {self.config_path}")
        except FileNotFoundError:
            logger.warning(f"Config file not found: {self.config_path}, using defaults")
            self.config = self._get_default_config()
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML config: {e}")
            raise ValueError(f"Invalid YAML configuration: {e}")

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "video": {
                "width": 640,
                "height": 360,
                "fps": 30.0,
                "address": "http://192.168.1.100/mjpeg/1",
                "buffer_size": 30,
            },
            "recording": {
                "output_folder": "./recordings/%Y-%m-%d",
                "duration_seconds": 120,
                "fourcc_codec": "avc1",
                "video_format": "mp4",
                "enable_deduplication": True,
                "dedup_threshold": 0.95,
            },
            "processing": {"enable_processing": False, "algorithms": []},
            "visualization": {"show_stream": False, "window_title": "VideoAPI Stream"},
            "logging": {"level": "INFO", "file": None, "enable_console": True},
        }

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation.

        Args:
            key: Configuration key (e.g., 'video.width')
            default: Default value if key not found

        Returns:
            Configuration value
        """
        keys = key.split(".")
        value = self.config

        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key: str, value: Any) -> None:
        """Set configuration value using dot notation.

        Args:
            key: Configuration key (e.g., 'video.width')
            value: Value to set
        """
        keys = key.split(".")
        config_dict = self.config

        for k in keys[:-1]:
            if k not in config_dict:
                config_dict[k] = {}
            config_dict = config_dict[k]

        config_dict[keys[-1]] = value

    def validate(self) -> bool:
        """Validate configuration values.

        Returns:
            True if configuration is valid
        """
        try:
            # Validate video settings
            width = self.get("video.width")
            height = self.get("video.height")
            if not isinstance(width, int) or width <= 0:
                raise ValueError("video.width must be a positive integer")
            if not isinstance(height, int) or height <= 0:
                raise ValueError("video.height must be a positive integer")

            # Validate recording settings
            duration = self.get("recording.duration_seconds")
            if not isinstance(duration, (int, float)) or duration <= 0:
                raise ValueError("recording.duration_seconds must be a positive number")

            fps = self.get("video.fps")
            if not isinstance(fps, (int, float)) or fps <= 0:
                raise ValueError("video.fps must be a positive number")

            buffer_size = self.get("video.buffer_size")
            if not isinstance(buffer_size, int) or buffer_size <= 0:
                raise ValueError("video.buffer_size must be a positive integer")

            return True
        except ValueError as e:
            logger.error(f"Configuration validation failed: {e}")
            return False

    def reload(self) -> None:
        """Reload configuration from file."""
        self._load_config()

    def save(self, path: Optional[Union[str, Path]] = None) -> None:
        """Save current configuration to file.

        Args:
            path: Path to save configuration. If None, uses original path.
        """
        save_path = path or self.config_path
        if save_path is None:
            raise ValueError("No save path specified")

        with open(save_path, "w") as file:
            yaml.dump(self.config, file, default_flow_style=False, indent=2)

        logger.info(f"Configuration saved to {save_path}")
