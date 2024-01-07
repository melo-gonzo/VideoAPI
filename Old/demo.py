import copy
import traceback
from collections import deque
import sys
sys.path.append("/usr/lib/python3/dist-packages")


import cv2
import numpy as np
import yaml

from utils.region_select import *
from video_api import TimeEvents, VideoStream


class Demo(VideoStream):

    def algorithm_thread(self):
        while True:
            try:
                if self.thread_manager["run_algo"]:
                    print("Running...", end="\r")
                    if self.verbose:
                        print(f"\nAlgo Current: {self.thread_manager}")
                    self.thread_manager = {
                        "grab_frame": False,
                        "run_algo": False,
                        "save_frame": True,
                    }
                    if self.verbose:
                        print(f"Algo Next Action: {self.thread_manager}")
                else:
                    pass
            except AttributeError:
                print(traceback.format_exc())
                pass




params = yaml.safe_load(open("params.yaml", "r"))
video_stream_params = params["video_stream_params"]
algo_params = params["algo_params"]
video_stream = Demo(video_stream_params=video_stream_params, **algo_params)
