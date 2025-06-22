"""Video stream visualization component."""

import cv2
import threading
import time
from typing import Optional, Dict, Any, Callable, Tuple
import numpy as np

from ..utils.logging_config import get_logger

logger = get_logger("visualization")


class StreamViewer:
    """Handles real-time video stream visualization."""

    def __init__(
        self,
        window_title: str = "VideoAPI Stream",
        window_size: Optional[Tuple[int, int]] = None,
        fps_display: bool = True,
        info_display: bool = True,
    ):
        """Initialize stream viewer.

        Args:
            window_title: Title of the display window
            window_size: (width, height) for window size, None for auto
            fps_display: Whether to display FPS counter
            info_display: Whether to display stream info overlay
        """
        self.window_title = window_title
        self.window_size = window_size
        self.fps_display = fps_display
        self.info_display = info_display

        # Display state
        self.showing = False
        self.window_created = False
        self.current_frame = None
        self.frame_lock = threading.Lock()

        # FPS calculation
        self.fps_counter = 0
        self.fps_last_time = time.time()
        self.display_fps = 0.0

        # Stream info
        self.stream_info = {}
        self.recording_info = {}

        # Callbacks
        self.key_callback: Optional[Callable[[int], bool]] = None
        self.mouse_callback: Optional[Callable[[int, int, int, int], None]] = None

        logger.info(f"StreamViewer initialized: {window_title}")

    def show(self) -> bool:
        """Show the visualization window.

        Returns:
            True if window was created successfully, False otherwise
        """
        if self.showing:
            return True

        try:
            cv2.namedWindow(self.window_title, cv2.WINDOW_AUTOSIZE)

            if self.window_size:
                cv2.resizeWindow(
                    self.window_title, self.window_size[0], self.window_size[1]
                )

            # Set mouse callback if provided
            if self.mouse_callback:
                cv2.setMouseCallback(self.window_title, self._mouse_handler)

            self.window_created = True
            self.showing = True

            logger.info("Stream viewer window created")
            return True

        except Exception as e:
            logger.error(f"Failed to create display window: {e}")
            return False

    def hide(self) -> None:
        """Hide the visualization window."""
        if not self.showing:
            return

        try:
            cv2.destroyWindow(self.window_title)
            self.window_created = False
            self.showing = False

            logger.info("Stream viewer window closed")

        except Exception as e:
            logger.error(f"Error closing window: {e}")

    def update_frame(
        self, frame: np.ndarray, frame_info: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update the displayed frame.

        Args:
            frame: Frame to display
            frame_info: Optional frame metadata
        """
        if not self.showing:
            return

        try:
            with self.frame_lock:
                # Create a copy for display
                display_frame = frame.copy()

                # Add overlays
                if self.fps_display or self.info_display:
                    display_frame = self._add_overlays(display_frame, frame_info)

                self.current_frame = display_frame

            # Update FPS counter
            self._update_fps()

        except Exception as e:
            logger.error(f"Error updating frame: {e}")

    def display(self) -> int:
        """Display the current frame and handle window events.

        Returns:
            Key code of pressed key, -1 if no key pressed, 27 (ESC) to quit
        """
        if not self.showing or self.current_frame is None:
            return -1

        try:
            with self.frame_lock:
                cv2.imshow(self.window_title, self.current_frame)

            # Handle key events
            key = cv2.waitKey(1) & 0xFF

            if key != 255:  # Key was pressed
                if self.key_callback:
                    try:
                        # If callback returns True, consume the key event
                        if self.key_callback(key):
                            return -1
                    except Exception as e:
                        logger.error(f"Error in key callback: {e}")

                return key

            return -1

        except Exception as e:
            logger.error(f"Error displaying frame: {e}")
            return -1

    def set_key_callback(self, callback: Callable[[int], bool]) -> None:
        """Set callback for key events.

        Args:
            callback: Function that takes key code and returns True to consume event
        """
        self.key_callback = callback

    def set_mouse_callback(
        self, callback: Callable[[int, int, int, int], None]
    ) -> None:
        """Set callback for mouse events.

        Args:
            callback: Function that takes (event, x, y, flags) parameters
        """
        self.mouse_callback = callback

        # Update OpenCV callback if window exists
        if self.window_created:
            cv2.setMouseCallback(self.window_title, self._mouse_handler)

    def _mouse_handler(self, event: int, x: int, y: int, flags: int) -> None:
        """Internal mouse event handler."""
        if self.mouse_callback:
            try:
                self.mouse_callback(event, x, y, flags)
            except Exception as e:
                logger.error(f"Error in mouse callback: {e}")

    def _add_overlays(
        self, frame: np.ndarray, frame_info: Optional[Dict[str, Any]] = None
    ) -> np.ndarray:
        """Add information overlays to frame.

        Args:
            frame: Input frame
            frame_info: Frame metadata

        Returns:
            Frame with overlays added
        """
        overlay_frame = frame.copy()
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6
        thickness = 1

        # Text properties
        text_color = (0, 255, 0)  # Green
        background_color = (0, 0, 0)  # Black

        y_offset = 25
        line_height = 25

        try:
            # FPS display
            if self.fps_display:
                fps_text = f"FPS: {self.display_fps:.1f}"
                self._draw_text_with_background(
                    overlay_frame,
                    fps_text,
                    (10, y_offset),
                    font,
                    font_scale,
                    text_color,
                    background_color,
                    thickness,
                )
                y_offset += line_height

            # Stream info display
            if self.info_display:
                # Frame counter
                if frame_info and "counter" in frame_info:
                    counter_text = f"Frame: {frame_info['counter']}"
                    self._draw_text_with_background(
                        overlay_frame,
                        counter_text,
                        (10, y_offset),
                        font,
                        font_scale,
                        text_color,
                        background_color,
                        thickness,
                    )
                    y_offset += line_height

                # Stream resolution
                height, width = frame.shape[:2]
                res_text = f"Resolution: {width}x{height}"
                self._draw_text_with_background(
                    overlay_frame,
                    res_text,
                    (10, y_offset),
                    font,
                    font_scale,
                    text_color,
                    background_color,
                    thickness,
                )
                y_offset += line_height

                # Recording status
                if self.recording_info.get("is_recording", False):
                    rec_text = "● REC"
                    rec_color = (0, 0, 255)  # Red
                    self._draw_text_with_background(
                        overlay_frame,
                        rec_text,
                        (10, y_offset),
                        font,
                        font_scale,
                        rec_color,
                        background_color,
                        thickness,
                    )
                    y_offset += line_height

                # Additional stream info
                for key, value in self.stream_info.items():
                    if key in ["fps", "width", "height"]:  # Already displayed
                        continue

                    info_text = f"{key}: {value}"
                    self._draw_text_with_background(
                        overlay_frame,
                        info_text,
                        (10, y_offset),
                        font,
                        font_scale * 0.8,
                        text_color,
                        background_color,
                        thickness,
                    )
                    y_offset += line_height

        except Exception as e:
            logger.error(f"Error adding overlays: {e}")

        return overlay_frame

    def _draw_text_with_background(
        self,
        img: np.ndarray,
        text: str,
        position: Tuple[int, int],
        font: int,
        font_scale: float,
        text_color: Tuple[int, int, int],
        bg_color: Tuple[int, int, int],
        thickness: int,
    ) -> None:
        """Draw text with background rectangle.

        Args:
            img: Image to draw on
            text: Text to draw
            position: (x, y) position
            font: OpenCV font type
            font_scale: Font scale factor
            text_color: Text color (B, G, R)
            bg_color: Background color (B, G, R)
            thickness: Text thickness
        """
        # Get text size
        (text_width, text_height), baseline = cv2.getTextSize(
            text, font, font_scale, thickness
        )

        x, y = position

        # Draw background rectangle
        cv2.rectangle(
            img,
            (x - 2, y - text_height - 2),
            (x + text_width + 2, y + baseline + 2),
            bg_color,
            -1,
        )

        # Draw text
        cv2.putText(img, text, (x, y), font, font_scale, text_color, thickness)

    def _update_fps(self) -> None:
        """Update FPS calculation."""
        current_time = time.time()
        self.fps_counter += 1

        time_diff = current_time - self.fps_last_time
        if time_diff >= 1.0:  # Update every second
            self.display_fps = self.fps_counter / time_diff
            self.fps_counter = 0
            self.fps_last_time = current_time

    def update_stream_info(self, info: Dict[str, Any]) -> None:
        """Update stream information for display.

        Args:
            info: Stream information dictionary
        """
        self.stream_info.update(info)

    def update_recording_info(self, info: Dict[str, Any]) -> None:
        """Update recording information for display.

        Args:
            info: Recording information dictionary
        """
        self.recording_info.update(info)

    def take_screenshot(self, filename: Optional[str] = None) -> Optional[str]:
        """Take a screenshot of the current frame.

        Args:
            filename: Output filename, auto-generated if None

        Returns:
            Filename of saved screenshot or None if failed
        """
        if self.current_frame is None:
            logger.warning("No frame available for screenshot")
            return None

        try:
            if filename is None:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f"screenshot_{timestamp}.png"

            with self.frame_lock:
                cv2.imwrite(filename, self.current_frame)

            logger.info(f"Screenshot saved: {filename}")
            return filename

        except Exception as e:
            logger.error(f"Error saving screenshot: {e}")
            return None

    def is_showing(self) -> bool:
        """Check if viewer window is currently showing."""
        return self.showing

    def get_display_info(self) -> Dict[str, Any]:
        """Get current display information."""
        return {
            "showing": self.showing,
            "window_title": self.window_title,
            "window_size": self.window_size,
            "fps_display": self.fps_display,
            "info_display": self.info_display,
            "current_fps": self.display_fps,
            "has_frame": self.current_frame is not None,
        }

    def cleanup(self) -> None:
        """Cleanup visualization resources."""
        self.hide()
        cv2.destroyAllWindows()
        logger.info("StreamViewer cleaned up")
