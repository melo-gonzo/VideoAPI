import os
import time
import traceback
from abc import ABC, abstractmethod
from threading import Thread

import cv2
import numpy as np
import yaml

from utils.time_utils import TimeEvents


class VideoStream(ABC):
    def __init__(self, video_stream_params={}, **kwargs):

        self.__dict__.update(kwargs)
        self.__dict__.update(video_stream_params)
        self.capture = cv2.VideoCapture(self.ip)
        self.ip = str(self.ip)
        self.status = False
        self.write_frame = False
        print(self.capture.isOpened())
        while not self.status:
            if self.capture.isOpened():
                print("Capture Open")
                (self.status, self.frame) = self.capture.read()

        time.sleep(0.1)
        self.frame_width = int(self.capture.get(3) * self.resize_multiplier)
        self.frame_height = int(self.capture.get(4) * self.resize_multiplier)
        self.frame = np.zeros((self.frame_width, self.frame_height))
        self.codec = cv2.VideoWriter_fourcc(
            "X", "V", "I", "D"
        )  # 'M', 'J', 'P', 'G', 'X', 'V', 'I', 'D
        self.status = True
        if self.playback:
            self.thread_manager = {
                "grab_frame": True,
                "run_algo": False,
                "save_frame": False,
            }
        else:
            self.thread_manager = {
                "grab_frame": True,
                "run_algo": True,
                "save_frame": True,
            }
        self.move_files()
        self.iterate_video()
        if self.visualize:
            cv2.namedWindow(self.frame_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(self.frame_name, (640, 480))
        ####
        self.thread = Thread(target=self.update, args=())
        self.thread.dameon = True
        self.thread.start()
        if self.save_video or self.show_algo:
            self.recording_thread = Thread(target=self.start_recording, args=())
            self.recording_thread.daemon = True
            self.recording_thread.start()
        time.sleep(0.1)
        self.algo_thread = Thread(target=self.algorithm_thread, args=())
        self.algo_thread.daemon = True
        self.algo_thread.start()
        ####
        print("Initialized {}".format(self.video_file))

    def iterate_video(self):
        start_time = time.strftime("%Y-%m-%dT%H%M%S", time.gmtime())
        if self.playback:
            self.frame_name = "_".join([self.name, self.algorithm, "Playback"])
            playback_file = self.ip.split("/")[-1]
            file_name_params = [
                self.name,
                self.algorithm,
                "Playback",
                playback_file[:-4],
                ".avi",
            ]
            self.video_file = self.storage_location + "_".join(file_name_params)
        else:
            self.frame_name = "_".join([self.name, self.algorithm, "Stream"])
            file_name_params = [self.name, self.algorithm, start_time, ".avi"]
            self.video_file = self.storage_location + "_".join(file_name_params)
        if self.save_logs:
            self.log_file = self.video_file.strip(".avi") + ".txt"
        if self.save_video:
            self.output_video = cv2.VideoWriter(
                self.video_file, self.codec, 10, (self.frame_width, self.frame_height)
            )

    def update(self):
        if self.capture.isOpened():
            (self.status, self.frame) = self.capture.read()
            if self.resize_multiplier != 1:
                self.frame = cv2.resize(
                    self.frame, (self.frame_width, self.frame_height)
                )
            if not self.status:
                os._exit(1)
        while self.status:
            time.sleep(self.extra_sleep)
            if self.capture.isOpened():
                if self.playback:
                    if self.thread_manager["grab_frame"]:
                        if self.verbose:
                            print(f"\nUpdate Current: {self.thread_manager}")
                        time.sleep(self.playback_rate)
                        (self.status, self.frame) = self.capture.read()
                        self.new_frame = self.write_frame = self.status
                        if self.resize_multiplier != 1:
                            self.frame = cv2.resize(
                                self.frame, (self.frame_width, self.frame_height)
                            )
                        self.thread_manager = {
                            "grab_frame": False,
                            "run_algo": True,
                            "save_frame": False,
                        }
                        if self.verbose:
                            print(f"Update Next Action: {self.thread_manager}\n")
                else:
                    (self.status, self.frame) = self.capture.read()
                    self.write_frame = self.status
                    self.thread_manager = {
                        "grab_frame": False,
                        "run_algo": True,
                        "save_frame": False,
                    }
                    if self.verbose:
                        print(f"Update Next Action : {self.thread_manager}\n")
                if not self.status:
                    os._exit(1)

    def show_frame(self):
        if all([self.status, self.visualize]):
            cv2.imshow(self.frame_name, self.frame)
        key = cv2.waitKey(1)
        if key == ord("q"):
            self.capture.release()
            self.output_video.release()
            cv2.destroyAllWindows()
            os._exit(1)

    def save_frame(self):
        if self.thread_manager["save_frame"] and self.write_frame:
            if self.verbose:
                print(f"\nSave Frame Current: {self.thread_manager}")
            self.output_video.write(self.frame)
            self.write_frame = False
            if self.playback:
                self.thread_manager = {
                    "grab_frame": True,
                    "run_algo": False,
                    "save_frame": False,
                }
            if self.verbose:
                print(f"Save Frame Next Action: {self.thread_manager}\n")

    def move_files(self):
        sl = self.storage_location
        for file in os.listdir(sl):
            os.replace(
                sl + file, sl + "sync/" + file
            ) if ".txt" in file or ".avi" in file else 0

    def start_recording(self):
        timer = TimeEvents().restart()
        while True:
            if timer.elapsed() > self.saved_video_length:
                self.move_files()
                timer = TimeEvents().restart()
                self.iterate_video()
            try:
                if self.show_algo:
                    self.show_frame()
                if self.save_video:
                    self.save_frame()
            except AttributeError:
                print(traceback.format_exc())
                pass

    def algorithm_thread(self):
        while True:
            if self.thread_manager["run_algo"]:
                if self.verbose:
                    print(f"\nAlgo Current: {self.thread_manager}")
                self.thread_manager = {
                    "grab_frame": False,
                    "run_algo": False,
                    "save_frame": True,
                }
                if self.verbose:
                    print(f"Algo Next Action: {self.thread_manager}\n")
        pass


if __name__ == "__main__":
    print("VideoAPI")
    params = yaml.safe_load(open("params.yaml", "r"))
    video_stream_params = params["video_stream_params"]
    algo_params = params["algo_params"]
    video_stream = VideoStream(video_stream_params=video_stream_params)
