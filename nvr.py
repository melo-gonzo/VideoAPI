import logging
import os
import sys
import threading
import time
from collections import deque
from datetime import datetime, timedelta

import cv2
import yaml

from creds import *

# os.environ["OPENCV_FFMPEG_DEBUG"] = "1"
# os.environ["GST_DEBUG"] = "4"  # Increase from 3 to 4 for more detail

logging.basicConfig(
    filename="/home/carmelog/Media/NVR/video_recording.log", level=logging.DEBUG
)


def nicetime():
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


logging.debug("%s: Starting VideoAPI", nicetime())

logging.getLogger().addHandler(logging.StreamHandler())


class VideoStream:
    def __init__(self, video_address, buffer_size=30):  # Increased buffer size
        self.video_address = video_address
        self.cap = None
        self.frame_buffer = deque(maxlen=buffer_size)
        self.frame_counter = 0
        self.last_frame_time = None
        self.frame_lock = threading.Lock()
        self.frame_available = threading.Condition(self.frame_lock)
        self.running = True
        self.thread = threading.Thread(target=self._read_frames)
        self.thread.daemon = True
        self.thread.start()

    def _initialize_capture(self):
        if self.cap is not None:
            self.cap.release()
        self.cap = cv2.VideoCapture(self.video_address)
        if not self.cap.isOpened():
            logging.error("%s: Failed to open video capture", nicetime())
            return False
        return True

    def _read_frames(self):
        while self.running:
            if not self._initialize_capture():
                time.sleep(5)
                continue

            while self.cap.isOpened() and self.running:
                ret, frame = self.cap.read()
                if ret:
                    current_time = time.time()
                    with self.frame_lock:
                        self.frame_buffer.append(
                            (self.frame_counter, frame.copy(), current_time)
                        )
                        self.frame_counter += 1
                        self.frame_available.notify()

                    self.last_frame_time = current_time
                else:
                    logging.debug(
                        "%s: Frame not available, reinitializing capture", nicetime()
                    )
                    break

            if not self.running:
                break
            time.sleep(1)

    def get_latest_frames(self, last_frame_counter=-1):
        """Get all frames since the last processed frame counter"""
        with self.frame_lock:
            while len(self.frame_buffer) == 0 and self.running:
                self.frame_available.wait(timeout=1.0)

            # Return all frames newer than last_frame_counter
            return [
                frame for frame in self.frame_buffer if frame[0] > last_frame_counter
            ]

    def stop(self):
        self.running = False
        with self.frame_lock:
            self.frame_available.notify_all()
        if self.cap is not None:
            self.cap.release()


class VideoRecorder:
    def __init__(self, width, height, output_folder, fourcc_codec, video_format):
        self.width = width
        self.height = height
        self.output_folder_base = output_folder
        self.output_folder = output_folder
        self.fourcc_codec = fourcc_codec
        self.video_format = video_format
        self.recording = False
        self.video_writer = None
        self.recording_start_time = None
        self.last_written_frame_counter = -1
        self.write_lock = threading.Lock()
        self.write_thread = None
        self.running = True

    def start_recording(self):
        try:
            current_time = datetime.now().strftime("%H-%M-%S")
            self.output_folder = datetime.now().strftime(self.output_folder_base)
            os.makedirs(self.output_folder, exist_ok=True)
            self.output_filename = (
                f"{self.output_folder}/{current_time}_c.{self.video_format}"
            )

            self.video_writer = cv2.VideoWriter(
                self.output_filename,
                cv2.VideoWriter_fourcc(*self.fourcc_codec),
                30.0,
                (self.width, self.height),
            )
            self.recording_start_time = datetime.now()
            self.recording = True

            # Start the write thread
            if self.write_thread is None:
                self.write_thread = threading.Thread(target=self._write_thread)
                self.write_thread.daemon = True
                self.write_thread.start()

            logging.debug("%s: Recording started: %s", nicetime(), self.output_filename)
        except Exception as e:
            logging.error(f"{nicetime()}: Recording failed to start: {str(e)}")

    def _write_thread(self):
        while self.running:
            if self.recording and hasattr(self, "frame_queue") and self.frame_queue:
                try:
                    frame_counter, frame, _ = self.frame_queue.popleft()
                    if frame_counter > self.last_written_frame_counter:
                        frame = cv2.resize(frame, (self.width, self.height))
                        with self.write_lock:
                            self.video_writer.write(frame)
                        self.last_written_frame_counter = frame_counter
                except Exception as e:
                    logging.error(f"{nicetime()}: Failed to write frame: {str(e)}")
            else:
                time.sleep(0.001)

    def write_frames(self, frames):
        """Queue multiple frames for writing"""
        if not hasattr(self, "frame_queue"):
            self.frame_queue = deque()

        for frame_data in frames:
            self.frame_queue.append(frame_data)

    def stop_recording(self):
        self.recording = False
        with self.write_lock:
            if self.video_writer is not None:
                self.video_writer.release()
                self.video_writer = None
        logging.debug("%s: Recording stopped", nicetime())

    def stop(self):
        self.running = False
        self.stop_recording()
        if self.write_thread:
            self.write_thread.join(timeout=1.0)

    def get_elapsed_time(self):
        return datetime.now() - self.recording_start_time


def read_video_stream(vs, video_recorder, recording_duration):
    try:
        while True:
            if video_recorder.recording:
                # Get all new frames since last written frame
                new_frames = vs.get_latest_frames(
                    video_recorder.last_written_frame_counter
                )
                if new_frames:
                    video_recorder.write_frames(new_frames)

                if video_recorder.get_elapsed_time() >= recording_duration:
                    video_recorder.stop_recording()
                    video_recorder.start_recording()

            time.sleep(0.001)  # Small delay to prevent busy-waiting
    except Exception as e:
        logging.error(f"{nicetime()}: Error in read_video_stream: {str(e)}")
        raise


def main():
    # Load parameters from YAML file
    with open("parameters.yaml", "r") as file:
        params = yaml.safe_load(file)

    # Get parameters from YAML
    width = params["window_width"]
    height = params["window_height"]
    video_address = params["video_address"].format(user=user, password=password)
    output_folder = params["output_folder"]
    fourcc_codec = params["fourcc_codec"]
    video_format = params["video_format"]
    recording_duration = timedelta(seconds=params["recording_duration"])

    vs = VideoStream(video_address)
    video_recorder = VideoRecorder(
        width, height, output_folder, fourcc_codec, video_format
    )

    try:
        # Start recording
        video_recorder.start_recording()

        # Start the reading thread
        read_thread = threading.Thread(
            target=read_video_stream, args=(vs, video_recorder, recording_duration)
        )
        read_thread.daemon = True
        read_thread.start()

        # Main loop
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("Stopping the recording...")
    finally:
        vs.stop()
        video_recorder.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    time.sleep(1)
    while True:
        try:
            main()
        except Exception as e:
            logging.error("%s: Error in main: %s", nicetime(), str(e))
            time.sleep(10)  # Wait before restarting the main function
