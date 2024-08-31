import sys

sys.path.append("/usr/lib/python3/dist-packages")

import logging
import os
import threading
import time
from datetime import datetime, timedelta
from collections import deque

import cv2
import yaml

from creds import *

os.environ["GST_DEBUG"] = "3"

logging.basicConfig(
    filename="/home/carmelog/Desktop/video_recording.log", level=logging.DEBUG
)


def nicetime():
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


logging.debug("%s: Starting VideoAPI", nicetime())


class VideoStream:
    def __init__(self, video_address, buffer_size=3):
        self.video_address = video_address
        self.cap = None
        self.frame_buffer = deque(maxlen=buffer_size)
        self.frame_counter = 0
        self.last_frame_hash = None
        self.frame_lock = threading.Lock()
        self.frame_available = threading.Event()
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
        while True:
            if not self._initialize_capture():
                time.sleep(5)  # Wait before retrying
                continue

            while self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret:
                    frame_hash = self._hash_frame(frame)
                    if frame_hash != self.last_frame_hash:
                        with self.frame_lock:
                            self.frame_buffer.append((self.frame_counter, frame))
                            self.frame_counter += 1
                        self.last_frame_hash = frame_hash
                        self.frame_available.set()
                else:
                    logging.debug("%s: Frame not available in _read_frames, reinitializing capture", nicetime())
                    break  # Break the inner loop to reinitialize capture

            time.sleep(1)  # Short delay before retrying


    def _hash_frame(self, frame):
        return hash(frame.tobytes())

    def get_latest_frame(self):
        self.frame_available.wait()
        with self.frame_lock:
            return self.frame_buffer[-1] if self.frame_buffer else (None, None)

class VideoRecorder:
    def __init__(self, width, height, output_folder, video_format):
        self.width = width
        self.height = height
        self.output_folder_base = output_folder
        self.output_folder = output_folder
        self.video_format = video_format
        self.recording = False
        self.output_filename = None
        self.video_writer = None
        self.recording_start_time = None
        self.last_written_frame_counter = -1

    @property
    def output_folder(self):
        return self._output_folder

    @output_folder.setter
    def output_folder(self, value):
        logging.debug("%s: Make output folder in output_folder", nicetime())
        self._output_folder = datetime.now().strftime(value)

    def start_recording(self):
        try:
            current_time = datetime.now().strftime("%H-%M-%S")
            self.output_folder = self.output_folder_base
            os.makedirs(self.output_folder, exist_ok=True)
            self.output_filename = (
                f"{self.output_folder}/{current_time}_c.{self.video_format}"
            )
            logging.debug(
                "%s: Saving to: %s in start_recording", nicetime(), self.output_filename
            )
            self.video_writer = cv2.VideoWriter(
                self.output_filename,
                cv2.VideoWriter_fourcc(*"mp4v"),
                30.0,
                (self.width, self.height),
            )
            self.recording_start_time = datetime.now()
            self.recording = True
            logging.debug("%s: Recording started in start_recording", nicetime())
        except Exception:
            logging.debug(
                "%s: Recording failed to start in start_recording", nicetime()
            )
            pass

    def stop_recording(self):
        if self.video_writer is not None:
            self.video_writer.release()
        self.recording = False
        logging.debug("%s: Recording stopped in stop_recording", nicetime())

    def is_recording(self):
        return self.recording

    def write_frame(self, frame_counter, frame):
        if frame is not None and frame_counter > self.last_written_frame_counter:
            try:
                frame = cv2.resize(frame, (self.width, self.height))
                self.video_writer.write(frame)
                self.last_written_frame_counter = frame_counter
            except Exception:
                logging.debug("%s: Failed to write frame in write_frame", nicetime())
                pass

    def get_elapsed_time(self):
        return datetime.now() - self.recording_start_time


def read_video_stream(vs, video_recorder, recording_duration):
    def write_frame_thread():
        while True:
            if video_recorder.is_recording():
                frame_counter, frame = vs.get_latest_frame()
                if frame is not None:
                    video_recorder.write_frame(frame_counter, frame)
            time.sleep(0.001)  # Small delay to prevent busy-waiting

    write_thread = threading.Thread(target=write_frame_thread)
    write_thread.daemon = True
    write_thread.start()

    while True:
        if video_recorder.is_recording():
            if video_recorder.get_elapsed_time() >= recording_duration:
                video_recorder.stop_recording()
                logging.debug(
                    "%s: Recording stopped after %s seconds",
                    nicetime(),
                    recording_duration,
                )
                video_recorder.start_recording()
        time.sleep(0.1)  # Check recording status less frequently


def main():
    # Load parameters from YAML file
    with open("parameters.yaml", "r") as file:
        params = yaml.safe_load(file)

    # Get parameters from YAML
    width = params["window_width"]
    height = params["window_height"]
    video_address = params["video_address"].format(user, password)
    output_folder = params["output_folder"]
    fourcc_codec = params["fourcc_codec"]
    show_stream = params["show_stream"]
    video_format = params["video_format"]
    recording_duration = params["recording_duration"]

    # Create a VideoStream object
    vs = VideoStream(video_address)
    if show_stream:
        cv2.namedWindow("Video Stream", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Video Stream", width, height)

    # Create the directory with the current date as the folder name
    # output_folder = os.path.join(output_folder, datetime.now().strftime("%Y-%m-%d"))

    # Create VideoRecorder object
    video_recorder = VideoRecorder(width, height, output_folder, video_format)
    time.sleep(3)
    # Create a separate thread for reading the video stream
    recording_duration = timedelta(seconds=recording_duration)
    thread = threading.Thread(
        target=read_video_stream, args=(vs, video_recorder, recording_duration)
    )
    thread.daemon = True
    thread.start()

    # Start recording
    video_recorder.start_recording()

    while True:
        frame = vs.get_latest_frame()

        if show_stream:
            # Display the frame
            cv2.imshow("Video Stream", frame)

            # Check for 'q' key press to exit
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    logging.debug("%s: Broken from main", nicetime())
    # Stop recording and release resources
    video_recorder.stop_recording()
    vs.cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    time.sleep(1)
    while True:
        try:
            main()
        except Exception as e:
            logging.error("%s: Error in main: %s", nicetime(), str(e))
            time.sleep(10)  # Wait before restarting the main function