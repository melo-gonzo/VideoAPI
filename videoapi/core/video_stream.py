"""Video stream capture and buffering."""

import cv2
import threading
import time
from collections import deque
from typing import List, Tuple, Optional, Dict, Any
import numpy as np

from videoapi.utils.logging_config import get_logger

logger = get_logger("video_stream")


class VideoStream:
    """Handles video stream capture with buffering and thread safety."""

    def __init__(
        self,
        video_address: str,
        buffer_size: int = 30,
        reconnect_delay: float = 5.0,
        max_reconnect_attempts: int = -1,
    ):
        """Initialize video stream.

        Args:
            video_address: Video source address (RTSP, HTTP, file path, etc.)
            buffer_size: Maximum number of frames to buffer
            reconnect_delay: Delay between reconnection attempts in seconds
            max_reconnect_attempts: Maximum reconnection attempts (-1 for unlimited)
        """
        self.video_address = video_address
        self.buffer_size = buffer_size
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_attempts = max_reconnect_attempts

        # Video capture
        self.cap = None
        self.frame_buffer = deque(maxlen=buffer_size)
        self.frame_counter = 0
        self.last_frame_time = None
        self.reconnect_count = 0

        # Threading
        self.frame_lock = threading.Lock()
        self.frame_available = threading.Condition(self.frame_lock)
        self.running = False
        self.thread = None

        # Stream info
        self.stream_info = {
            "fps": None,
            "width": None,
            "height": None,
            "total_frames": None,
        }

        logger.info(f"VideoStream initialized for {video_address}")

    def start(self) -> bool:
        """Start video stream capture.

        Returns:
            True if stream started successfully, False otherwise
        """
        if self.running:
            logger.warning("Video stream is already running")
            return True

        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()

        # Wait a moment to see if initialization succeeds
        time.sleep(0.5)

        with self.frame_lock:
            success = len(self.frame_buffer) > 0 or self.cap is not None

        if success:
            logger.info("Video stream started successfully")
        else:
            logger.error("Failed to start video stream")
            self.stop()

        return success

    def stop(self) -> None:
        """Stop video stream capture."""
        if not self.running:
            return

        logger.info("Stopping video stream...")
        self.running = False

        # Notify waiting threads
        with self.frame_lock:
            self.frame_available.notify_all()

        # Wait for thread to finish
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)

        # Release capture
        if self.cap is not None:
            self.cap.release()
            self.cap = None

        logger.info("Video stream stopped")

    def _capture_loop(self) -> None:
        """Main capture loop running in separate thread."""
        while self.running:
            if not self._initialize_capture():
                if self._should_reconnect():
                    time.sleep(self.reconnect_delay)
                    continue
                else:
                    logger.error("Max reconnection attempts reached, stopping stream")
                    break

            # Reset reconnect count on successful connection
            self.reconnect_count = 0

            while self.cap and self.cap.isOpened() and self.running:
                ret, frame = self.cap.read()

                if ret and frame is not None:
                    current_time = time.time()

                    with self.frame_lock:
                        frame_data = (self.frame_counter, frame.copy(), current_time)
                        self.frame_buffer.append(frame_data)
                        self.frame_counter += 1
                        self.frame_available.notify_all()

                    self.last_frame_time = current_time

                else:
                    logger.debug("Frame not available, connection lost")
                    break

            # Clean up current capture before reconnecting
            if self.cap is not None:
                self.cap.release()
                self.cap = None

    def _initialize_capture(self) -> bool:
        """Initialize video capture.

        Returns:
            True if capture initialized successfully, False otherwise
        """
        try:
            if self.cap is not None:
                self.cap.release()

            logger.debug(f"Attempting to connect to {self.video_address}")
            self.cap = cv2.VideoCapture(self.video_address)

            if not self.cap.isOpened():
                logger.warning(f"Failed to open video capture for {self.video_address}")
                return False

            # Get stream information
            self._update_stream_info()

            logger.info("Video capture initialized successfully")
            logger.debug(f"Stream info: {self.stream_info}")

            return True

        except Exception as e:
            logger.error(f"Error initializing video capture: {e}")
            return False

    def _update_stream_info(self) -> None:
        """Update stream information from capture."""
        if self.cap is None:
            return

        try:
            self.stream_info.update(
                {
                    "fps": self.cap.get(cv2.CAP_PROP_FPS),
                    "width": int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                    "height": int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                    "total_frames": int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT)),
                }
            )
        except Exception as e:
            logger.warning(f"Could not retrieve stream info: {e}")

    def _should_reconnect(self) -> bool:
        """Check if should attempt reconnection.

        Returns:
            True if should reconnect, False otherwise
        """
        if self.max_reconnect_attempts == -1:
            return True

        if self.reconnect_count < self.max_reconnect_attempts:
            self.reconnect_count += 1
            logger.info(
                f"Reconnection attempt {self.reconnect_count}/{self.max_reconnect_attempts}"
            )
            return True

        return False

    def get_latest_frames(
        self, last_frame_counter: int = -1
    ) -> List[Tuple[int, np.ndarray, float]]:
        """Get all frames since the last processed frame counter.

        Args:
            last_frame_counter: Last processed frame counter

        Returns:
            List of (frame_counter, frame, timestamp) tuples
        """
        with self.frame_lock:
            # Wait for frames if buffer is empty
            while len(self.frame_buffer) == 0 and self.running:
                if not self.frame_available.wait(timeout=1.0):
                    break

            # Return frames newer than last_frame_counter
            return [
                frame_data
                for frame_data in self.frame_buffer
                if frame_data[0] > last_frame_counter
            ]

    def get_latest_frame(self) -> Optional[Tuple[int, np.ndarray, float]]:
        """Get the most recent frame.

        Returns:
            (frame_counter, frame, timestamp) tuple or None if no frames available
        """
        with self.frame_lock:
            if len(self.frame_buffer) == 0:
                return None
            return self.frame_buffer[-1]

    def wait_for_frame(self, timeout: float = 1.0) -> bool:
        """Wait for a new frame to be available.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if frame became available, False on timeout
        """
        with self.frame_lock:
            if len(self.frame_buffer) > 0:
                return True
            return self.frame_available.wait(timeout=timeout)

    def get_buffer_size(self) -> int:
        """Get current number of frames in buffer."""
        with self.frame_lock:
            return len(self.frame_buffer)

    def get_stream_info(self) -> Dict[str, Any]:
        """Get stream information."""
        return self.stream_info.copy()

    def is_running(self) -> bool:
        """Check if stream is running."""
        return self.running

    def is_connected(self) -> bool:
        """Check if stream is connected."""
        return self.cap is not None and self.cap.isOpened()

    def get_stats(self) -> Dict[str, Any]:
        """Get stream statistics."""
        with self.frame_lock:
            buffer_size = len(self.frame_buffer)

        return {
            "frame_counter": self.frame_counter,
            "buffer_size": buffer_size,
            "max_buffer_size": self.buffer_size,
            "last_frame_time": self.last_frame_time,
            "reconnect_count": self.reconnect_count,
            "is_running": self.running,
            "is_connected": self.is_connected(),
            "stream_info": self.stream_info,
        }
