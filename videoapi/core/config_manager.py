"""Configuration management for VideoAPI."""

import yaml
from typing import Dict, Any, Optional, Union
from pathlib import Path

from videoapi.utils.logging_config import get_logger

logger = get_logger("config")


class ConfigManager:
    """Manages configuration loading and validation."""

    def __init__(
        self,
        config_path: Optional[Union[str, Path]] = None,
        creds_path: Optional[Union[str, Path]] = None,
    ):
        """Initialize ConfigManager.

        Args:
            config_path: Path to configuration file
            creds_path: Path to credentials file
        """
        self.config_path = config_path
        self.creds_path = creds_path
        self.config = {}
        self.credentials = {}

        self._load_config()
        self._load_credentials()

    def _load_credentials(self) -> None:
        """Load credentials from file."""
        if self.creds_path is None:
            logger.info("No credentials file found")
            return

        try:
            with open(self.creds_path, "r") as file:
                self.credentials = yaml.safe_load(file) or {}
            logger.info(f"Loaded credentials from {self.creds_path}")
        except FileNotFoundError:
            logger.warning(f"Credentials file not found: {self.creds_path}")
            self.credentials = {}
        except yaml.YAMLError as e:
            logger.error(f"Error parsing credentials YAML: {e}")
            self.credentials = {}
        except Exception as e:
            logger.error(f"Error loading credentials: {e}")
            self.credentials = {}

    def get_camera_credentials(self, camera_id: str) -> Dict[str, str]:
        """Get credentials for a specific camera.

        Args:
            camera_id: Camera identifier

        Returns:
            Dictionary with username and password
        """
        cameras = self.credentials.get("cameras", {})

        if camera_id in cameras:
            creds = cameras[camera_id]
            return {
                "username": creds.get("username", ""),
                "password": creds.get("password", ""),
            }

        # Fall back to default credentials
        default_creds = self.credentials.get("default", {})
        return {
            "username": default_creds.get("username", ""),
            "password": default_creds.get("password", ""),
        }

    def build_rtsp_url(self, template_name: str, camera_id: str, **kwargs) -> str:
        """Build RTSP URL using template and credentials.

        Args:
            template_name: Name of URL template to use
            camera_id: Camera identifier for credentials
            **kwargs: Additional parameters for URL template

        Returns:
            Complete RTSP URL with credentials
        """
        templates = self.credentials.get("templates", {})
        if template_name not in templates:
            raise ValueError(f"URL template '{template_name}' not found")

        template = templates[template_name]

        # Get credentials
        creds = self.get_camera_credentials(camera_id)

        # Combine credentials with other parameters
        url_params = {**creds, **kwargs}

        try:
            return template.format(**url_params)
        except KeyError as e:
            raise ValueError(f"Missing parameter for URL template: {e}")

    def build_simple_rtsp_url(
        self,
        ip: str,
        camera_id: str = "default",
        port: int = 554,
        path: str = "",
        **kwargs,
    ) -> str:
        """Build a simple RTSP URL with credentials.

        Args:
            ip: Camera IP address
            camera_id: Camera identifier for credentials
            port: RTSP port (default 554)
            path: URL path after the port
            **kwargs: Additional parameters

        Returns:
            Complete RTSP URL
        """
        creds = self.get_camera_credentials(camera_id)

        if path:
            return f"rtsp://{creds['username']}:{creds['password']}@{ip}:{port}/{path}"
        else:
            return f"rtsp://{creds['username']}:{creds['password']}@{ip}:{port}"

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
            if duration is not None and (
                not isinstance(duration, (int, float)) or duration <= 0
            ):
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

    def get_video_address(self) -> str:
        """Get the resolved video address with credentials.

        Returns:
            Complete video source address
        """
        source_config = self.get("video.source")

        if not source_config:
            # Fallback to legacy direct address
            return self.get("video.address", "")

        source_type = source_config.get("type", "direct")

        if source_type == "direct":
            return source_config.get("address", "")

        elif source_type == "rtsp_simple":
            return self.build_simple_rtsp_url(
                ip=source_config["ip"],
                camera_id=source_config.get("camera_id", "default"),
                port=source_config.get("port", 554),
                path=source_config.get("path", ""),
            )

        elif source_type == "rtsp_template":
            template_params = {
                k: v
                for k, v in source_config.items()
                if k not in ["type", "template", "camera_id"]
            }

            return self.build_rtsp_url(
                template_name=source_config["template"],
                camera_id=source_config.get("camera_id", "default"),
                **template_params,
            )

        else:
            raise ValueError(f"Unknown video source type: {source_type}")
