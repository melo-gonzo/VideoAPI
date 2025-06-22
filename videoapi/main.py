"""Main entry point for VideoAPI application."""

import argparse
import signal
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import timedelta

from videoapi.core.config_manager import ConfigManager
from videoapi.core.video_stream import VideoStream
from videoapi.core.video_recorder import VideoRecorder
from videoapi.core.frame_processor import FrameProcessor
from videoapi.core.playback_manager import PlaybackManager
from videoapi.algorithms.frame_deduplicator import FrameDeduplicator
from videoapi.visualization.stream_viewer import StreamViewer
from videoapi.utils.logging_config import setup_logging, get_logger

logger = get_logger("main")


class VideoAPIApp:
    """Main VideoAPI application coordinator."""

    def __init__(
        self, config_path: Optional[str] = None, creds_path: Optional[str] = None
    ):
        """Initialize VideoAPI application.

        Args:
            config_path: Path to configuration file
            creds_path: Path to credentials file
        """
        self.config = ConfigManager(config_path, creds_path)  # Pass both paths

        # Validate configuration
        if not self.config.validate():
            raise ValueError("Invalid configuration")

        # Setup logging
        setup_logging(
            log_file=self.config.get("logging.file"),
            log_level=self.config.get("logging.level", "INFO"),
            enable_console=self.config.get("logging.enable_console", True),
        )

        # Initialize components
        self.video_stream: Optional[VideoStream] = None
        self.video_recorder: Optional[VideoRecorder] = None
        self.frame_processor: Optional[FrameProcessor] = None
        self.playback_manager: Optional[PlaybackManager] = None
        self.stream_viewer: Optional[StreamViewer] = None

        # Application state
        self.running = False
        self.mode = "live"  # "live" or "playback"

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info("VideoAPI application initialized")

    def setup_live_mode(self) -> None:
        """Setup components for live video processing."""
        self.mode = "live"

        # Get resolved video address with credentials
        video_address = self.config.get_video_address()

        # Initialize video stream with output resolution
        self.video_stream = VideoStream(
            video_address=video_address,  # Use resolved address
            buffer_size=self.config.get("video.buffer_size", 30),
            reconnect_delay=5.0,
            max_reconnect_attempts=-1,
            output_width=self.config.get("video.width"),
            output_height=self.config.get("video.height"),
        )

        # Initialize video recorder if recording is enabled
        recording_config = self.config.get("recording", {})
        if recording_config:
            self.video_recorder = VideoRecorder(
                width=self.config.get("video.width"),
                height=self.config.get("video.height"),
                output_folder=recording_config.get(
                    "output_folder", "./recordings/%Y-%m-%d"
                ),
                fourcc_codec=recording_config.get("fourcc_codec", "mp4v"),
                video_format=recording_config.get("video_format", "mp4"),
                fps=self.config.get("video.fps", 30.0),
                recording_duration=None
                if recording_config.get("duration_seconds") is None
                else timedelta(seconds=recording_config["duration_seconds"]),
                enable_deduplication=recording_config.get("enable_deduplication", True),
                dedup_config={
                    "threshold": recording_config.get("dedup_threshold", 0.95)
                },
            )

        # Initialize frame processor if processing is enabled
        if self.config.get("processing.enable_processing", False):
            self.frame_processor = FrameProcessor(max_queue_size=100)

            # Add deduplication algorithm if not already in recorder
            if not self.video_recorder or not self.video_recorder.enable_deduplication:
                dedup_algo = FrameDeduplicator(
                    {"threshold": self.config.get("recording.dedup_threshold", 0.95)}
                )
                self.frame_processor.add_algorithm(dedup_algo)

        # Initialize stream viewer if visualization is enabled
        if self.config.get("visualization.show_stream", False):
            # Use video dimensions as default window size
            video_width = self.config.get("video.width", 640)
            video_height = self.config.get("video.height", 360)

            self.stream_viewer = StreamViewer(
                window_title=self.config.get(
                    "visualization.window_title", "VideoAPI Stream"
                ),
                window_size=(video_width, video_height),  # Set default window size
                show_fps=self.config.get("visualization.show_fps", True),
                show_info=self.config.get("visualization.show_info", True),
                show_recording_status=self.config.get(
                    "visualization.show_recording_status", True
                ),
                show_frame_counter=self.config.get(
                    "visualization.show_frame_counter", False
                ),
                show_resolution=self.config.get("visualization.show_resolution", False),
                show_stream_fps=self.config.get("visualization.show_stream_fps", False),
            )
            self.stream_viewer.set_key_callback(self._handle_key_press)

        logger.info("Live mode setup complete")

    def setup_playback_mode(self, video_path: str, loop: bool = False) -> None:
        """Setup components for video playback.

        Args:
            video_path: Path to video file
            loop: Whether to loop playback
        """
        self.mode = "playback"

        # Initialize playback manager
        self.playback_manager = PlaybackManager(video_path, loop=loop)
        self.playback_manager.set_frame_callback(self._handle_playback_frame)

        # Initialize frame processor if processing is enabled
        if self.config.get("processing.enable_processing", False):
            self.frame_processor = FrameProcessor(max_queue_size=100)

        # Initialize stream viewer if visualization is enabled
        if self.config.get("visualization.show_stream", False):
            self.stream_viewer = StreamViewer(
                window_title=f"VideoAPI Playback - {Path(video_path).name}",
            )
            self.stream_viewer.set_key_callback(self._handle_playback_key_press)

        logger.info(f"Playback mode setup complete for {video_path}")

    def start(self) -> bool:
        """Start the VideoAPI application.

        Returns:
            True if started successfully, False otherwise
        """
        if self.running:
            logger.warning("Application is already running")
            return True

        try:
            self.running = True

            if self.mode == "live":
                return self._start_live_mode()
            elif self.mode == "playback":
                return self._start_playback_mode()
            else:
                logger.error(f"Unknown mode: {self.mode}")
                return False

        except Exception as e:
            logger.error(f"Error starting application: {e}")
            self.running = False
            return False

    def _start_live_mode(self) -> bool:
        """Start live video processing."""
        # Start video stream
        if not self.video_stream.start():
            logger.error("Failed to start video stream")
            return False

        # Start frame processor
        if self.frame_processor:
            self.frame_processor.start()

        # Start video recorder
        if self.video_recorder:
            if not self.video_recorder.start_recording():
                logger.error("Failed to start video recording")
                return False

        # Show stream viewer
        if self.stream_viewer:
            if not self.stream_viewer.show():
                logger.error("Failed to show stream viewer")
                return False

        logger.info("Live mode started successfully")
        return True

    def _start_playback_mode(self) -> bool:
        """Start video playback."""
        # Start frame processor
        if self.frame_processor:
            self.frame_processor.start()

        # Show stream viewer
        if self.stream_viewer:
            if not self.stream_viewer.show():
                logger.error("Failed to show stream viewer")
                return False

        # Start playback
        if not self.playback_manager.start():
            logger.error("Failed to start video playback")
            return False

        logger.info("Playback mode started successfully")
        return True

    def run(self) -> None:
        """Run the main application loop."""
        if not self.running:
            logger.error("Application not started")
            return

        logger.info("Starting main application loop")

        try:
            if self.mode == "live":
                self._run_live_loop()
            elif self.mode == "playback":
                self._run_playback_loop()
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        finally:
            self.stop()

    def _run_live_loop(self) -> None:
        """Main loop for live video processing."""
        last_frame_counter = -1

        while self.running:
            try:
                # Get new frames from stream
                if self.video_stream and self.video_stream.is_running():
                    new_frames = self.video_stream.get_latest_frames(last_frame_counter)

                    if new_frames:
                        # Update last processed frame
                        last_frame_counter = new_frames[-1][0]

                        # Send frames to recorder
                        if self.video_recorder and self.video_recorder.is_recording():
                            self.video_recorder.write_frames(new_frames)

                        # Send frames to processor
                        if self.frame_processor:
                            for frame_counter, frame, timestamp in new_frames:
                                frame_info = {
                                    "counter": frame_counter,
                                    "timestamp": timestamp,
                                    "source": "live_stream",
                                }
                                self.frame_processor.submit_frame(frame, frame_info)

                        # Update visualization
                        if self.stream_viewer and self.stream_viewer.is_showing():
                            latest_frame = new_frames[-1]
                            frame_info = {
                                "counter": latest_frame[0],
                                "timestamp": latest_frame[2],
                            }
                            self.stream_viewer.update_frame(latest_frame[1], frame_info)

                            # Update stream info
                            self.stream_viewer.update_stream_info(
                                self.video_stream.get_stream_info()
                            )
                            if self.video_recorder:
                                self.stream_viewer.update_recording_info(
                                    self.video_recorder.get_stats()
                                )

                # Handle visualization
                if self.stream_viewer and self.stream_viewer.is_showing():
                    key = self.stream_viewer.display()
                    if key == 27:  # ESC key
                        logger.info("ESC pressed, stopping application")
                        break

                time.sleep(0.01)  # Small delay to prevent busy waiting

            except Exception as e:
                logger.error(f"Error in live loop: {e}")
                time.sleep(1)

    def _run_playback_loop(self) -> None:
        """Main loop for video playback."""
        while self.running:
            try:
                # Handle visualization
                if self.stream_viewer and self.stream_viewer.is_showing():
                    key = self.stream_viewer.display()
                    if key == 27:  # ESC key
                        logger.info("ESC pressed, stopping application")
                        break

                # Check if playback finished
                if (
                    self.playback_manager
                    and not self.playback_manager.get_playback_info()["playing"]
                ):
                    logger.info("Playback finished")
                    break

                time.sleep(0.01)

            except Exception as e:
                logger.error(f"Error in playback loop: {e}")
                time.sleep(1)

    def _handle_playback_frame(self, frame, frame_info):
        """Handle frame from playback manager."""
        try:
            # Send to processor
            if self.frame_processor:
                self.frame_processor.submit_frame(frame, frame_info)

            # Update visualization
            if self.stream_viewer and self.stream_viewer.is_showing():
                self.stream_viewer.update_frame(frame, frame_info)

        except Exception as e:
            logger.error(f"Error handling playback frame: {e}")

    def _handle_key_press(self, key: int) -> bool:
        """Handle key press events for live mode.

        Args:
            key: Key code

        Returns:
            True to consume the key event, False to pass through
        """
        if key == ord("q"):
            logger.info("Q pressed, stopping application")
            self.running = False
            return True
        elif key == ord("s") and self.stream_viewer:
            # Take screenshot
            self.stream_viewer.take_screenshot()
            return True
        elif key == ord("r") and self.video_recorder:
            # Toggle recording
            if self.video_recorder.is_recording():
                self.video_recorder.stop_recording()
                logger.info("Recording stopped by user")
            else:
                self.video_recorder.start_recording()
                logger.info("Recording started by user")
            return True

        return False

    def _handle_playback_key_press(self, key: int) -> bool:
        """Handle key press events for playback mode.

        Args:
            key: Key code

        Returns:
            True to consume the key event, False to pass through
        """
        if key == ord("q"):
            logger.info("Q pressed, stopping application")
            self.running = False
            return True
        elif key == ord(" ") and self.playback_manager:
            # Toggle pause
            info = self.playback_manager.get_playback_info()
            if info["paused"]:
                self.playback_manager.resume()
            else:
                self.playback_manager.pause()
            return True
        elif key == ord("s") and self.stream_viewer:
            # Take screenshot
            self.stream_viewer.take_screenshot()
            return True

        return False

    def stop(self) -> None:
        """Stop the VideoAPI application."""
        if not self.running:
            return

        logger.info("Stopping VideoAPI application...")
        self.running = False

        # Stop components
        if self.video_stream:
            self.video_stream.stop()

        if self.video_recorder:
            self.video_recorder.stop()

        if self.frame_processor:
            self.frame_processor.stop()

        if self.playback_manager:
            self.playback_manager.stop()

        if self.stream_viewer:
            self.stream_viewer.cleanup()

        logger.info("VideoAPI application stopped")

    def _signal_handler(self, signum, frame):
        """Handle system signals."""
        logger.info(f"Received signal {signum}")
        self.running = False

    def get_stats(self) -> Dict[str, Any]:
        """Get application statistics."""
        stats = {
            "mode": self.mode,
            "running": self.running,
            "config": self.config.config,
        }

        if self.video_stream:
            stats["video_stream"] = self.video_stream.get_stats()

        if self.video_recorder:
            stats["video_recorder"] = self.video_recorder.get_stats()

        if self.frame_processor:
            stats["frame_processor"] = self.frame_processor.get_stats()

        if self.playback_manager:
            stats["playback"] = self.playback_manager.get_playback_info()

        if self.stream_viewer:
            stats["visualization"] = self.stream_viewer.get_display_info()

        return stats


def main():
    """Main entry point for the VideoAPI command line interface."""
    parser = argparse.ArgumentParser(
        description="VideoAPI - Video streaming and recording tool"
    )

    parser.add_argument("-c", "--config", type=str, help="Configuration file path")
    parser.add_argument("--creds", type=str, help="Credentials file path")
    parser.add_argument(
        "-p", "--playback", type=str, help="Video file path for playback mode"
    )
    parser.add_argument(
        "--loop", action="store_true", help="Loop playback (playback mode only)"
    )
    parser.add_argument(
        "--no-display", action="store_true", help="Disable video display"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level",
    )

    args = parser.parse_args()

    try:
        # Create application with both config and creds paths
        app = VideoAPIApp(args.config, args.creds)  # Fixed: pass both arguments

        # Override display setting if specified
        if args.no_display:
            app.config.set("visualization.show_stream", False)

        # Override log level if specified
        app.config.set("logging.level", args.log_level)

        # Setup mode
        if args.playback:
            if not Path(args.playback).exists():
                logger.error(f"Video file not found: {args.playback}")
                sys.exit(1)
            app.setup_playback_mode(args.playback, args.loop)
        else:
            app.setup_live_mode()

        # Start and run application
        if app.start():
            app.run()
        else:
            logger.error("Failed to start application")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
