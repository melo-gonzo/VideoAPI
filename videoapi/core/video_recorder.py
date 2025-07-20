"""Video recording with deduplication and threading."""

import cv2
import os
import threading
from collections import deque
from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Dict, Any
import numpy as np

from videoapi.algorithms.frame_deduplicator import FrameDeduplicator
from videoapi.utils.logging_config import get_logger
from videoapi.utils.frame_utils import resize_frame

logger = get_logger("video_recorder")


class VideoRecorder:
    """Handles video recording with deduplication and automatic file rotation."""

    def __init__(
        self,
        width: int,
        height: int,
        output_folder: str,
        fourcc_codec: str = "mp4v",
        video_format: str = "mp4",
        fps: float = 30.0,
        recording_duration: Optional[timedelta] = None,
        enable_deduplication: bool = True,
        dedup_config: Optional[Dict[str, Any]] = None,
        max_write_queue_size: int = 300,
    ):
        """Initialize video recorder.

        Args:
            width: Output video width
            height: Output video height
            output_folder: Base output folder (supports strftime formatting)
            fourcc_codec: Video codec fourcc code
            video_format: Video file format/extension
            fps: Output video frame rate
            recording_duration: Duration before starting new file (None for no rotation)
            enable_deduplication: Whether to enable frame deduplication
            dedup_config: Configuration for deduplication algorithm
            max_write_queue_size: Maximum frames to queue for writing
        """
        self.width = width
        self.height = height
        self.output_folder_base = output_folder
        self.output_folder = output_folder
        self.fourcc_codec = fourcc_codec
        self.video_format = video_format
        self.fps = fps
        self.recording_duration = recording_duration
        self.max_write_queue_size = max_write_queue_size

        # Recording state
        self.recording = False
        self.video_writer = None
        self.current_filename = None
        self.recording_start_time = None
        self.last_written_frame_counter = -1

        # Frame deduplication
        self.enable_deduplication = enable_deduplication
        if self.enable_deduplication:
            self.deduplicator = FrameDeduplicator(dedup_config)
        else:
            self.deduplicator = None

        # Threading
        self.write_queue = deque(maxlen=max_write_queue_size)
        self.write_lock = threading.Lock()
        self.queue_condition = threading.Condition(self.write_lock)
        self.write_thread = None
        self.running = True

        # Statistics
        self.total_frames_received = 0
        self.total_frames_written = 0
        self.total_frames_dropped = 0
        self.files_created = 0

        logger.info(f"VideoRecorder initialized: {width}x{height} @ {fps}fps")

    def start_recording(self) -> bool:
        """Start video recording.

        Returns:
            True if recording started successfully, False otherwise
        """
        if self.recording:
            logger.warning("Recording is already active")
            return True

        try:
            # Create output directory
            self.output_folder = datetime.now().strftime(self.output_folder_base)
            os.makedirs(self.output_folder, exist_ok=True)

            # Generate filename
            current_time = datetime.now().strftime("%H-%M-%S")
            self.current_filename = (
                f"{self.output_folder}/{current_time}_c.{self.video_format}"
            )

            # Initialize video writer
            fourcc = cv2.VideoWriter_fourcc(*self.fourcc_codec)
            self.video_writer = cv2.VideoWriter(
                self.current_filename, fourcc, self.fps, (self.width, self.height)
            )

            if not self.video_writer.isOpened():
                logger.error(f"Failed to open video writer for {self.current_filename}")
                return False

            self.recording_start_time = datetime.now()
            self.recording = True
            self.files_created += 1

            # Start write thread if not already running
            if self.write_thread is None or not self.write_thread.is_alive():
                self.write_thread = threading.Thread(
                    target=self._write_loop, daemon=True
                )
                self.write_thread.start()

            logger.info(f"Recording started: {self.current_filename}")
            return True

        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            self.recording = False
            return False

    def stop_recording(self) -> None:
        """Stop current recording."""
        if not self.recording:
            return

        logger.info("Stopping recording...")
        self.recording = False

        # Wait for write queue to empty
        with self.write_lock:
            while len(self.write_queue) > 0:
                if not self.queue_condition.wait(timeout=1.0):
                    break

        # Release video writer
        if self.video_writer is not None:
            self.video_writer.release()
            self.video_writer = None

        logger.info(f"Recording stopped. File: {self.current_filename}")

    def stop(self) -> None:
        """Stop recorder completely."""
        logger.info("Stopping video recorder...")
        self.running = False
        self.stop_recording()

        # Notify write thread
        with self.write_lock:
            self.queue_condition.notify_all()

        # Wait for write thread to finish
        if self.write_thread and self.write_thread.is_alive():
            self.write_thread.join(timeout=3.0)

        # Cleanup deduplicator
        if self.deduplicator:
            self.deduplicator.cleanup()

        logger.info("Video recorder stopped")

    def write_frames(self, frames: List[Tuple[int, np.ndarray, float]]) -> int:
        """Queue multiple frames for writing.

        Args:
            frames: List of (frame_counter, frame, timestamp) tuples

        Returns:
            Number of frames actually queued
        """
        if not self.recording:
            return 0

        frames_queued = 0

        with self.write_lock:
            for frame_counter, frame, timestamp in frames:
                # Skip frames we've already processed
                if frame_counter <= self.last_written_frame_counter:
                    continue

                self.total_frames_received += 1

                # Check for deduplication
                if self.enable_deduplication and self.deduplicator:
                    frame_info = {"counter": frame_counter, "timestamp": timestamp}

                    dedup_result = self.deduplicator.process(frame, frame_info)
                    if dedup_result.get("is_duplicate", False):
                        logger.debug(f"Skipping duplicate frame {frame_counter}")
                        self.last_written_frame_counter = frame_counter
                        continue

                # Check queue capacity
                if len(self.write_queue) >= self.max_write_queue_size:
                    self.total_frames_dropped += 1
                    logger.debug("Write queue full, dropping frame")
                    continue

                # Add to write queue
                self.write_queue.append((frame_counter, frame, timestamp))
                frames_queued += 1

            if frames_queued > 0:
                self.queue_condition.notify()

        return frames_queued

    def _write_loop(self) -> None:
        """Main write loop running in separate thread."""
        while self.running:
            frame_data = None

            with self.write_lock:
                while len(self.write_queue) == 0 and self.running:
                    if not self.queue_condition.wait(timeout=1.0):
                        continue

                if len(self.write_queue) > 0:
                    frame_data = self.write_queue.popleft()
                    self.queue_condition.notify()  # Notify that space is available

            if frame_data is None:
                continue

            frame_counter, frame, timestamp = frame_data

            try:
                # Check if we need to rotate files
                if self._should_rotate_file():
                    self.stop_recording()
                    if not self.start_recording():
                        logger.error("Failed to rotate recording file")
                        break

                # Write frame
                if self.recording and self.video_writer is not None:
                    # Resize frame if necessary
                    if frame.shape[:2] != (self.height, self.width):
                        frame = resize_frame(frame, self.width, self.height)

                    self.video_writer.write(frame)
                    self.total_frames_written += 1
                    self.last_written_frame_counter = frame_counter

            except Exception as e:
                logger.error(f"Error writing frame {frame_counter}: {e}")

    def _should_rotate_file(self) -> bool:
        """Check if current file should be rotated.

        Returns:
            True if file should be rotated, False otherwise
        """
        if not self.recording or self.recording_duration is None:
            return False

        if self.recording_start_time is None:
            return False

        elapsed = datetime.now() - self.recording_start_time
        return elapsed >= self.recording_duration

    def get_elapsed_time(self) -> Optional[timedelta]:
        """Get elapsed recording time for current file.

        Returns:
            Elapsed time or None if not recording
        """
        if not self.recording or self.recording_start_time is None:
            return None

        return datetime.now() - self.recording_start_time

    def get_current_filename(self) -> Optional[str]:
        """Get current recording filename.

        Returns:
            Current filename or None if not recording
        """
        return self.current_filename if self.recording else None

    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self.recording

    def get_stats(self) -> Dict[str, Any]:
        """Get recording statistics."""
        with self.write_lock:
            queue_size = len(self.write_queue)

        stats = {
            "is_recording": self.recording,
            "current_filename": self.current_filename,
            "elapsed_time": self.get_elapsed_time(),
            "total_frames_received": self.total_frames_received,
            "total_frames_written": self.total_frames_written,
            "total_frames_dropped": self.total_frames_dropped,
            "files_created": self.files_created,
            "write_queue_size": queue_size,
            "max_write_queue_size": self.max_write_queue_size,
            "last_written_frame_counter": self.last_written_frame_counter,
        }

        # Add deduplication stats if enabled
        if self.deduplicator:
            stats["deduplication"] = self.deduplicator.get_stats()

        return stats

    def reset_stats(self) -> None:
        """Reset recording statistics."""
        self.total_frames_received = 0
        self.total_frames_written = 0
        self.total_frames_dropped = 0
        self.files_created = 0

        if self.deduplicator:
            self.deduplicator.reset_stats()

        logger.info("Recording statistics reset")

    def update_dedup_config(self, config: Dict[str, Any]) -> None:
        """Update deduplication configuration.

        Args:
            config: New deduplication configuration
        """
        if self.deduplicator:
            self.deduplicator.update_config(config)
            logger.info("Deduplication configuration updated")
        else:
            logger.warning("Deduplication is not enabled")
