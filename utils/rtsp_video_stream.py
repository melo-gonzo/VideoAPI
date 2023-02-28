import cv2


class VideoStreamer:
    def __init__(self):
        self.ip = "rtsp://192.168.1.15:8554/mjpeg/1"
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
            self.output_video.release()
            cv2.destroyAllWindows()


v = VideoStreamer()
