import sys
sys.path.append("/usr/lib/python3/dist-packages")
import cv2
import threading 
import os
import yaml
from datetime import datetime

class VideoStream:
    def __init__(self, video_address):
        self.cap = cv2.VideoCapture(video_address)
        self.frame = None
        self.frame_available = threading.Event()
        self.thread = threading.Thread(target=self._read_frames)
        self.thread.daemon = True
        self.thread.start()

    def _read_frames(self):
        while True:
            ret, frame = self.cap.read()
            if not ret:
                break
            self.frame = frame
            self.frame_available.set()
            self.frame_available.wait()

    def get_latest_frame(self):
        self.frame_available.wait()
        self.frame_available.clear()
        return self.frame

class VideoRecorder:
    def __init__(self, width, height, output_folder, recording_duration, fourcc_codec):
        self.width = width
        self.height = height
        self.output_folder = output_folder
        self.recording_duration = recording_duration
        self.fourcc_codec = cv2.VideoWriter_fourcc(*fourcc_codec)

        self.recording = False
        self.recording_start_time = None
        self.output_filename = None
        self.video_writer = None

    def start_recording(self):
        current_time = datetime.now().strftime("%H-%M-%S")
        self.output_filename = f"{self.output_folder}/{current_time}.mp4"
        self.video_writer = cv2.VideoWriter(
            self.output_filename,
            self.fourcc_codec,
            20.0,
            (self.width, self.height)
        )
        self.recording_start_time = datetime.now()
        self.recording = True
        print("Recording started.")

    def stop_recording(self):
        self.video_writer.release()
        self.recording = False
        print("Recording stopped.")

    def is_recording(self):
        return self.recording

    def write_frame(self, frame):
        self.video_writer.write(frame)

    def get_elapsed_time(self):
        return (datetime.now() - self.recording_start_time).total_seconds()

# Load parameters from YAML file
with open("parameters.yaml", "r") as file:
    params = yaml.safe_load(file)

# Get parameters from YAML
width = params["window_width"]
height = params["window_height"]
video_address = params["video_address"]
output_folder = datetime.now().strftime(params["output_folder"])
recording_duration = params["recording_duration"]
fourcc_codec = params["fourcc_codec"]

# Create a VideoStream object
vs = VideoStream(video_address)

# Set the window size
cv2.namedWindow("Video Stream", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Video Stream", width, height)

# Create the directory with current date as the folder name
os.makedirs(output_folder, exist_ok=True)

# Create VideoRecorder object
video_recorder = VideoRecorder(width, height, output_folder, recording_duration, fourcc_codec)

while True:
    frame = vs.get_latest_frame()

    # Display the frame
    cv2.imshow("Video Stream", frame)

    # Start/stop recording when 'r' key is pressed
    key = cv2.waitKey(1) & 0xFF
    if not video_recorder.is_recording():
        video_recorder.start_recording()

    if video_recorder.is_recording():
        print('write frame')
        video_recorder.write_frame(frame)

        if video_recorder.get_elapsed_time() >= recording_duration:
            video_recorder.stop_recording()
            print(f"Recording stopped after {recording_duration} seconds.")

    # Check for 'q' key press to exit
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Release the video capture and close all windows
vs.cap.release()
cv2.destroyAllWindows()