import sys

sys.path.append("/usr/lib/python3/dist-packages")

import os
import threading
import time
from datetime import datetime, timedelta

import cv2
import yaml

from creds import *

os.environ["GST_DEBUG"] = "3"

class VideoStream:
    def __init__(self, video_address):
        self.cap = cv2.VideoCapture(video_address)
        self.frame = None
        self.frame_available = threading.Event()
        self.thread = threading.Thread(target=self._read_frames)
        self.thread.daemon = True
        self.thread.start()

    def _read_frames(self):
        ret = False
        while not ret:
            if self.cap.isOpened():
                ret, frame = self.cap.read()

        while ret:
            ret, frame = self.cap.read()
            time.sleep(0.001)
            if ret:
                self.frame = frame
                self.frame_available.set()
                self.frame_available.wait()
            else:
                self.frame_available.wait()

    def get_latest_frame(self):
        self.frame_available.wait()
        self.frame_available.clear()
        return self.frame

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

    @property
    def output_folder(self):
        return self._output_folder

    @output_folder.setter
    def output_folder(self, value):
        self._output_folder = datetime.now().strftime(value)

    def start_recording(self):
        current_time = datetime.now().strftime("%H-%M-%S")
        self.output_folder = self.output_folder_base
        os.makedirs(self.output_folder, exist_ok=True)
        self.output_filename = f"{self.output_folder}/{current_time}_c.{self.video_format}"
        print(f"Saving to: {self.output_filename}")
        self.video_writer = cv2.VideoWriter(
            self.output_filename,
            cv2.VideoWriter_fourcc(*"mp4v"),
            20.0,
            (self.width, self.height),
        )
        self.recording_start_time = datetime.now()
        self.recording = True
        print("Recording started.")

    def stop_recording(self):
        if self.video_writer is not None:
            self.video_writer.release()
        self.recording = False
        print("Recording stopped.")

    def is_recording(self):
        return self.recording

    def write_frame(self, frame):
        if frame is not None:
            frame = cv2.resize(frame, (self.width, self.height))
            try:
                self.video_writer.write(frame)
            except Exception:
                pass

            
    def get_elapsed_time(self):
        return datetime.now() - self.recording_start_time

def read_video_stream(vs, video_recorder, recording_duration):
    while True:
        frame = vs.get_latest_frame()
        time.sleep(0.001)
        if video_recorder.is_recording():
            video_recorder.write_frame(frame)

            if video_recorder.get_elapsed_time() >= recording_duration:
                video_recorder.stop_recording()
                print(f"Recording stopped after {recording_duration} seconds.")
                video_recorder.start_recording()
                

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
    thread = threading.Thread(target=read_video_stream, args=(vs, video_recorder, recording_duration))
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
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    # Stop recording and release resources
    video_recorder.stop_recording()
    vs.cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    time.sleep(1)
    main()