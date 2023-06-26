import sys
sys.path.append("/usr/lib/python3/dist-packages")

import cv2
from creds import *


class VideoStreamer:
    def __init__(self, ip):
        self.ip = ip
        self.frame_name = "Carmelo"
        self.capture = cv2.VideoCapture(self.ip)
        (self.status, self.frame) = self.capture.read()
        while self.status:
            if self.capture.isOpened():
                print(
                    f"Capture Open {self.capture.isOpened()} and Streaming {self.status}",
                    end="\r",
                )
                (self.status, self.frame) = self.capture.read()
                if self.status:
                    self.show_frame()

    def show_frame(self):
        cv2.imshow(self.frame_name, self.frame)
        key = cv2.waitKey(1)
        if key == ord("q"):
            self.capture.release()
            cv2.destroyAllWindows()



ip = f"rtsp://{user}:{password}@192.168.1.17:554/cam/realmonitor?channel=1&subtype=1"

v = VideoStreamer(ip)
