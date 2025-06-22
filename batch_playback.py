#!/usr/bin/env python3
"""Batch process multiple video files."""

import sys
from pathlib import Path
from videoapi.main import VideoAPIApp


def process_video_directory(recordings_dir: str, config_path: str = None):
    """Process all videos in a directory."""
    recordings_path = Path(recordings_dir)

    if not recordings_path.exists():
        print(f"Directory not found: {recordings_dir}")
        return

    # Find all video files
    video_extensions = [".mp4", ".avi", ".mov", ".mkv"]
    video_files = []

    for ext in video_extensions:
        video_files.extend(recordings_path.rglob(f"*{ext}"))

    print(f"Found {len(video_files)} video files")

    for video_file in video_files:
        print(f"\nProcessing: {video_file}")

        try:
            # Create app instance
            app = VideoAPIApp(config_path)
            app.setup_playback_mode(str(video_file), loop=False)

            # For batch processing, disable visualization
            app.config.set("visualization.show_stream", False)

            if app.start():
                app.run()  # This will process the entire video

        except KeyboardInterrupt:
            print("Interrupted by user")
            break
        except Exception as e:
            print(f"Error processing {video_file}: {e}")
            continue


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python batch_playback.py <recordings_directory> [config_file]")
        sys.exit(1)

    recordings_dir = sys.argv[1]
    config_file = sys.argv[2] if len(sys.argv) > 2 else None

    process_video_directory(recordings_dir, config_file)
