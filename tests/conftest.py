"""Pytest configuration and fixtures for VideoAPI tests."""

import pytest
import tempfile
import numpy as np
import cv2
from pathlib import Path
from typing import Generator
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from videoapi.core.config_manager import ConfigManager


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as temp_path:
        yield Path(temp_path)


@pytest.fixture
def sample_config() -> dict:
    """Sample configuration for testing."""
    return {
        "video": {
            "width": 640,
            "height": 480,
            "fps": 30.0,
            "address": "test://dummy",
            "buffer_size": 10,
        },
        "recording": {
            "output_folder": "./test_recordings",
            "duration_seconds": 60,
            "fourcc_codec": "mp4v",
            "video_format": "mp4",
            "enable_deduplication": True,
            "dedup_threshold": 0.95,
        },
        "processing": {"enable_processing": False, "algorithms": []},
        "visualization": {"show_stream": False, "window_title": "Test Window"},
        "logging": {"level": "DEBUG", "file": None, "enable_console": False},
    }


@pytest.fixture
def config_manager(sample_config, temp_dir) -> ConfigManager:
    """Create a ConfigManager instance with test configuration."""
    config_file = temp_dir / "test_config.yaml"

    import yaml

    with open(config_file, "w") as f:
        yaml.dump(sample_config, f)

    return ConfigManager(str(config_file))


@pytest.fixture
def sample_frame() -> np.ndarray:
    """Create a sample video frame for testing."""
    # Create a 640x480 BGR frame with some pattern
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    # Add some pattern to make it recognizable
    cv2.rectangle(frame, (100, 100), (540, 380), (255, 255, 255), -1)
    cv2.rectangle(frame, (200, 200), (440, 280), (0, 255, 0), -1)
    cv2.putText(frame, "TEST", (250, 250), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 3)

    return frame


@pytest.fixture
def sample_frames(sample_frame) -> list:
    """Create a list of sample frames with slight variations."""
    frames = []
    base_frame = sample_frame.copy()

    for i in range(5):
        frame = base_frame.copy()
        # Add slight variation
        cv2.circle(frame, (320 + i * 10, 240), 5, (255, 0, 0), -1)
        frames.append(frame)

    return frames


@pytest.fixture
def test_video_file(temp_dir, sample_frames) -> Path:
    """Create a test video file."""
    video_path = temp_dir / "test_video.mp4"

    # Create video writer
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(video_path), fourcc, 30.0, (640, 480))

    # Write frames multiple times to create a longer video
    for _ in range(10):
        for frame in sample_frames:
            out.write(frame)

    out.release()

    return video_path


@pytest.fixture(autouse=True)
def setup_test_logging():
    """Setup logging for tests."""
    import logging

    logging.getLogger("videoapi").setLevel(
        logging.CRITICAL
    )  # Suppress logs during tests


@pytest.fixture
def mock_video_capture(monkeypatch):
    """Mock cv2.VideoCapture for testing."""

    class MockVideoCapture:
        def __init__(self, source):
            self.source = source
            self.opened = True
            self.frame_count = 0
            self.properties = {
                cv2.CAP_PROP_FPS: 30.0,
                cv2.CAP_PROP_FRAME_WIDTH: 640,
                cv2.CAP_PROP_FRAME_HEIGHT: 480,
                cv2.CAP_PROP_FRAME_COUNT: 100,
            }

        def isOpened(self):
            return self.opened

        def read(self):
            if self.frame_count < 100:
                # Return a dummy frame
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                frame.fill(self.frame_count % 255)
                self.frame_count += 1
                return True, frame
            return False, None

        def get(self, prop):
            return self.properties.get(prop, 0)

        def set(self, prop, value):
            self.properties[prop] = value
            return True

        def release(self):
            self.opened = False

    monkeypatch.setattr("cv2.VideoCapture", MockVideoCapture)
    return MockVideoCapture
