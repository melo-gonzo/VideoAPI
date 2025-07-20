"""Video file playback management."""

import cv2
import threading
import time
from typing import Optional, Dict, Any, Callable
import numpy as np
from pathlib import Path

from videoapi.utils.logging_config import get_logger

logger = get_logger("playback")


class PlaybackManager:
    """Manages video file playback with control features."""

    def __init__(self, video_path: str, loop: bool = False):
        """Initialize playback manager.

        Args:
            video_path: Path to video file
            loop: Whether to loop playback
        """
        self.video_path = video_path
        self.loop = loop

        # Video capture
        self.cap = None
        self.video_info = {}

        # Playback state
        self.playing = False
        self.paused = False
        self.current_frame = 0
        self.playback_speed = 1.0
        self.target_fps = 30.0

        # Threading
        self.playback_thread = None
        self.running = False
        self.playback_lock = threading.Lock()

        # Callbacks
        self.frame_callback: Optional[Callable[[np.ndarray, Dict[str, Any]], None]] = (
            None
        )
        self.end_callback: Optional[Callable[[], None]] = None

        # Initialize video
        self._initialize_video()

        logger.info(f"PlaybackManager initialized for {video_path}")

    def _initialize_video(self) -> bool:
        """Initialize video capture and get video information.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            if not Path(self.video_path).exists():
                logger.error(f"Video file not found: {self.video_path}")
                return False

            self.cap = cv2.VideoCapture(self.video_path)

            if not self.cap.isOpened():
                logger.error(f"Failed to open video file: {self.video_path}")
                return False

            # Get video information
            self.video_info = {
                "fps": self.cap.get(cv2.CAP_PROP_FPS),
                "width": int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                "height": int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                "total_frames": int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT)),
                "duration": 0.0,
            }

            # Calculate duration
            if self.video_info["fps"] > 0:
                self.video_info["duration"] = (
                    self.video_info["total_frames"] / self.video_info["fps"]
                )

            self.target_fps = (
                self.video_info["fps"] if self.video_info["fps"] > 0 else 30.0
            )

            logger.info(f"Video info: {self.video_info}")
            return True

        except Exception as e:
            logger.error(f"Error initializing video: {e}")
            return False

    def set_frame_callback(
        self, callback: Callable[[np.ndarray, Dict[str, Any]], None]
    ) -> None:
        """Set callback function for frame delivery.

        Args:
            callback: Function to call with each frame and frame info
        """
        self.frame_callback = callback

    def set_end_callback(self, callback: Callable[[], None]) -> None:
        """Set callback function for playback end.

        Args:
            callback: Function to call when playback ends
        """
        self.end_callback = callback

    def start(self) -> bool:
        """Start playback.

        Returns:
            True if playback started successfully, False otherwise
        """
        if not self.cap or not self.cap.isOpened():
            logger.error("Video not properly initialized")
            return False

        if self.playing:
            logger.warning("Playback is already running")
            return True

        with self.playback_lock:
            self.playing = True
            self.paused = False
            self.running = True

        self.playback_thread = threading.Thread(target=self._playback_loop, daemon=True)
        self.playback_thread.start()

        logger.info("Playback started")
        return True

    def stop(self) -> None:
        """Stop playback."""
        if not self.playing:
            return

        logger.info("Stopping playback...")

        with self.playback_lock:
            self.playing = False
            self.running = False

        # Wait for playback thread to finish
        if self.playback_thread and self.playback_thread.is_alive():
            self.playback_thread.join(timeout=2.0)

        logger.info("Playback stopped")

    def pause(self) -> None:
        """Pause playback."""
        with self.playback_lock:
            if self.playing:
                self.paused = True
                logger.info("Playback paused")

    def resume(self) -> None:
        """Resume playback."""
        with self.playback_lock:
            if self.playing:
                self.paused = False
                logger.info("Playback resumed")

    def seek(self, frame_number: int) -> bool:
        """Seek to specific frame.

        Args:
            frame_number: Frame number to seek to

        Returns:
            True if seek successful, False otherwise
        """
        if not self.cap:
            return False

        frame_number = max(0, min(frame_number, self.video_info["total_frames"] - 1))

        try:
            with self.playback_lock:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
                self.current_frame = frame_number

            logger.debug(f"Seeked to frame {frame_number}")
            return True

        except Exception as e:
            logger.error(f"Error seeking to frame {frame_number}: {e}")
            return False

    def seek_time(self, seconds: float) -> bool:
        """Seek to specific time position.

        Args:
            seconds: Time in seconds to seek to

        Returns:
            True if seek successful, False otherwise
        """
        if self.video_info["fps"] <= 0:
            return False

        frame_number = int(seconds * self.video_info["fps"])
        return self.seek(frame_number)

    def set_speed(self, speed: float) -> None:
        """Set playback speed.

        Args:
            speed: Playback speed multiplier (1.0 = normal speed)
        """
        with self.playback_lock:
            self.playback_speed = max(
                0.1, min(speed, 10.0)
            )  # Clamp between 0.1x and 10x

        logger.info(f"Playback speed set to {self.playback_speed}x")

    def _playback_loop(self) -> None:
        """Main playback loop running in separate thread."""
        frame_interval = 1.0 / (self.target_fps * self.playback_speed)
        last_frame_time = time.time()

        while self.running:
            with self.playback_lock:
                if self.paused:
                    time.sleep(frame_interval)
                    continue

                if not self.playing:
                    break

            # Read next frame
            ret, frame = self.cap.read()

            if ret:
                current_time = time.time()

                # Frame timing
                with self.playback_lock:
                    actual_interval = 1.0 / (self.target_fps * self.playback_speed)

                # Call frame callback
                if self.frame_callback:
                    frame_info = {
                        "frame_number": self.current_frame,
                        "timestamp": current_time,
                        "fps": self.video_info["fps"],
                        "playback_speed": self.playback_speed,
                    }

                    try:
                        self.frame_callback(frame, frame_info)
                    except Exception as e:
                        logger.error(f"Error in frame callback: {e}")

                with self.playback_lock:
                    self.current_frame += 1

                # Frame rate control
                elapsed = current_time - last_frame_time
                sleep_time = actual_interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

                last_frame_time = time.time()

            else:
                # End of video
                if self.loop:
                    logger.info("Looping video playback")
                    self.seek(0)
                else:
                    logger.info("Playback finished")
                    with self.playback_lock:
                        self.playing = False

                    # Call end callback
                    if self.end_callback:
                        try:
                            self.end_callback()
                        except Exception as e:
                            logger.error(f"Error in end callback: {e}")
                    break

    def get_current_frame_data(self) -> Optional[np.ndarray]:
        """Get current frame without advancing playback.

        Returns:
            Current frame or None if not available
        """
        if not self.cap:
            return None

        try:
            # Save current position
            current_pos = self.cap.get(cv2.CAP_PROP_POS_FRAMES)

            # Read frame at current position
            ret, frame = self.cap.read()

            # Restore position
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, current_pos)

            return frame if ret else None

        except Exception as e:
            logger.error(f"Error getting current frame: {e}")
            return None

    def get_video_info(self) -> Dict[str, Any]:
        """Get video information."""
        return self.video_info.copy()

    def get_playback_info(self) -> Dict[str, Any]:
        """Get current playback information."""
        with self.playback_lock:
            current_time = (
                self.current_frame / self.video_info["fps"]
                if self.video_info["fps"] > 0
                else 0
            )

            return {
                "playing": self.playing,
                "paused": self.paused,
                "current_frame": self.current_frame,
                "total_frames": self.video_info["total_frames"],
                "current_time": current_time,
                "total_time": self.video_info["duration"],
                "playback_speed": self.playback_speed,
                "progress": self.current_frame
                / max(1, self.video_info["total_frames"]),
            }

    def cleanup(self) -> None:
        """Cleanup resources."""
        self.stop()

        if self.cap:
            self.cap.release()
            self.cap = None

        logger.info("PlaybackManager cleaned up")
