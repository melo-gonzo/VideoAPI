import copy
import traceback
from collections import deque

import cv2
import numpy as np
import yaml

from utils.region_select import *
from video_api import TimeEvents, VideoStream


class Demo(VideoStream):

    def algorithm_thread(self):
        self.clip_frames = deque(maxlen=5)
        self.set_si_dict()
        self.global_timer = TimeEvents(name="Global")
        self.motion_timers = [TimeEvents(name=name) for name in self.roi_names]
        self.img_old = np.zeros_like(self.frame[:, :, 0])
        self.algorithm_frame = np.zeros_like(self.frame)
        if self.save_logs:
            self.write_data_headers()
        while True:
            try:
                if self.thread_manager["run_algo"]:
                    print("Running...", end="\r")
                    if self.verbose:
                        print(f"\nAlgo Current: {self.thread_manager}")
                    self.reset_si_dict()
                    self.algorithm_frame = self.frame.copy()
                    gray = cv2.cvtColor(self.algorithm_frame, cv2.COLOR_BGR2GRAY)
                    gray = cv2.GaussianBlur(gray, (self.blur, self.blur), 0)
                    frame_delta = cv2.absdiff(self.img_old, gray)
                    self.img_old = gray
                    thresh = cv2.threshold(
                        frame_delta, self.move_thresh, 255, cv2.THRESH_BINARY
                    )[1]
                    thresh = cv2.dilate(thresh, None, iterations=2)
                    diffs = cv2.findContours(
                        thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                    )[0]
                    self.get_motion(diffs, self.min_area, frame_delta)
                    motion = self.report_motion()
                    self.clip_frames.append(self.algorithm_frame)
                    ######################
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    bottomLeftCornerOfText = (10, 25)
                    fontScale = 0.75
                    fontColor = (255, 255, 255)
                    thickness = 1
                    lineType = 2
                    text = time.strftime("%Y-%m-%dT%H%M%S", time.localtime())
                    cv2.putText(
                        self.frame,
                        text,
                        bottomLeftCornerOfText,
                        font,
                        fontScale,
                        fontColor,
                        thickness,
                        lineType,
                    )
                    if motion:
                        report_time = time.strftime("%Y-%m-%dT%H%M%SZ", time.gmtime())
                        print(f"\nMotion: {report_time} \n", end="\r")
                        cv2.imwrite(
                            f"{self.storage_location}/images/{report_time}.jpg",
                            self.frame,
                        )
                        self.make_clip(self.clip_frames, report_time)
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

    def make_clip(self, frames, time):
        height, width = frames[0].shape[:2]
        # Create a VideoWriter object with the output filename and frame rate
        fourcc = cv2.VideoWriter_fourcc("X", "V", "I", "D")  # use appropriate codec
        output_filename = f"{self.storage_location}/images/{time}_clip.avi"
        fps = 2
        video_writer = cv2.VideoWriter(output_filename, fourcc, fps, (width, height))
        # Loop through the frames and write them to the video file
        for frame in frames:
            video_writer.write(frame)
        # Release the VideoWriter object and close the output file
        video_writer.release()

    def report_motion(self):
        self.new_frame = False
        flag_regions = []
        si_to_see = False
        for idx, region in enumerate(self.roi_names):
            if self.verbose:
                pass
                # print((self.motion_timers[idx].occurrences,
                #      self.motion_timers[idx].frames))
            reset_timer_condition = (
                self.motion_timers[idx].occurrences > 1
                and self.motion_timers[idx].frames == 0
            )
            if (
                reset_timer_condition
                and self.si_dict[region]["message_type"] == "Event"
            ):
                si_to_see = True
                self.motion_timers[idx].count_frames()
            if self.motion_timers[idx].frames > 0:
                self.motion_timers[idx].count_frames()
                if self.motion_timers[idx].frames > self.cooldown_frames:
                    self.motion_timers[idx].reset_frames()
            if (
                self.si_dict[region]["motion_flag"]
                or self.si_dict[region]["message_type"] == "Event"
            ):
                flag_regions.append(region)

        report_time = time.strftime("%Y-%m-%dT%H%M%SZ", time.gmtime())
        if self.save_logs and flag_regions != []:
            self.write_data(report_time=report_time)

        self.global_timer.count_frames()
        if self.global_timer.frames > self.cooldown_frames:
            self.global_timer.reset_frames()
            if self.save_logs:
                self.write_data(report_time=report_time, region="Z")
        self.new_frame = False
        return si_to_see

    def get_motion(self, diffs, min_area, frame_delta):
        good_locs = []
        bad_locs = []
        any_flag = False
        for motion_region in diffs:
            if cv2.contourArea(motion_region) > min_area:
                (x, y, w, h) = cv2.boundingRect(motion_region)
                center = (int(x + w / 2), int(y + h / 2))
                region = self.si_dict["roi_mask"][center]
                if region in self.roi_names:
                    good_locs.append([x, y, w, h])
                    self.si_dict[region]["motion_locs"].append(center)
                    self.si_dict[region]["motion_flag"] = True
                    self.si_dict[region]["message_type"] = "Event"
                else:
                    bad_locs.append([x, y, w, h])
        if self.show_algo:
            cv2.drawContours(self.frame, self.motion_roi, -1, (255, 0, 0), 2)
            if good_locs != []:
                for x, y, w, h in good_locs:
                    cv2.rectangle(self.frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            if bad_locs != []:
                for x, y, w, h in bad_locs:
                    cv2.rectangle(self.frame, (x, y), (x + w, y + h), (0, 0, 255), 2)

        for idx, region in enumerate(self.roi_names):
            roi_array = self.si_dict[region]["roi_array"]
            roi_array_ = frame_delta[roi_array[:, 1], roi_array[:, 0]]
            a = roi_array_.argmax()
            self.si_dict[region]["motion_max_delta"].append(
                np.round(roi_array_[a] / 255, 3)
            )
            self.si_dict[region]["motion_max_delta_idx"].append(
                [roi_array[a, 0], roi_array[a, 1]]
            )
            if self.si_dict[region]["motion_flag"]:
                self.motion_timers[idx].increment()
            else:
                self.motion_timers[idx].reset_increment()
        return

    def reset_si_dict(self):
        dict_keys = {
            "motion_locs": [],
            "object_locs": [],
            "object_type": [],
            "object_confidence": [],
            "motion_flag": None,
            "motion_max_delta": [],
            "motion_max_delta_idx": [],
            "message_type": [],
        }
        for region in self.roi_names:
            for key in dict_keys.keys():
                self.si_dict[region][key] = copy.deepcopy(dict_keys[key])

    def set_si_dict(self):
        mm_names, motion_regions, motion_roi, mpa, path = set_region_roi(
            self.name, self.frame_width, self.frame_height
        )
        self.roi_names = mm_names
        self.si_dict = {}
        dict_keys = {
            "motion_locs": [],
            "object_locs": [],
            "object_type": [],
            "object_confidence": [],
            "motion_flag": None,
            "motion_max_delta": [],
            "motion_max_delta_idx": [],
            "message_type": [],
        }
        for region in self.roi_names:
            self.si_dict[region] = copy.deepcopy(dict_keys)
        xy_list = [
            (x, y) for x in range(self.frame_width) for y in range(self.frame_height)
        ]
        self.si_dict["roi_mask"] = dict(zip(xy_list, [None] * len(xy_list)))
        for idx, region in enumerate(self.roi_names):
            self.si_dict[region]["roi_array"] = mpa[idx]
            for xy in mpa[idx]:
                self.si_dict["roi_mask"][tuple(xy)] = region

        self.motion_regions = motion_regions
        self.motion_roi = motion_roi
        self.full_frame = False

    def write_data_headers(self):
        with open(self.si_file, "a") as file:
            headers = [
                "Time",
                "Region",
                "Object",
                "Confidence",
                "Location",
                "MessageType",
            ]
            file.write(",".join(headers) + "\n")

    def write_data(self, report_time=0, region=""):
        # headers: Time, Region, Object, Confidence, Location, MessageType
        with open(self.si_file, "a") as file:
            if not self.playback:
                report_time = time.strftime("%Y-%m-%dT%H%M%SZ", time.gmtime())
            for region in self.roi_names:
                out_data = [report_time, region]
                if self.si_dict[region]["object_type"] != []:
                    for idx, obj in enumerate(self.si_dict[region]["object_type"]):
                        out_data = [report_time, region]
                        out_data.append(obj)
                        out_data.append(
                            str(self.si_dict[region]["object_confidence"][idx])
                        )
                        x, y = self.si_dict[region]["object_locs"][idx]
                        out_data.append(str(x) + "-" + str(y))
                        out_data.append(self.si_dict[region]["message_type"][idx])
                        file.write(",".join(out_data) + "\n")
                else:
                    out_data.extend(["None", "100", "None", "Observation"])
                    file.write(",".join(out_data) + "\n")


params = yaml.safe_load(open("params.yaml", "r"))
video_stream_params = params["video_stream_params"]
algo_params = params["algo_params"]
video_stream = Demo(video_stream_params=video_stream_params, **algo_params)
