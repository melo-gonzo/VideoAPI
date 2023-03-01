import os
import sys
import time

import cv2
import matplotlib.path as mplPath
import numpy as np


def set_region_roi(region, frame_width, frame_height):
    scale1 = 1
    scale2 = 1
    motion_roi = None
    motion_mask_names = [""]
    path = None
    mpa = None
    motion_regions = None
    if type(region) is tuple:
        region = region[0]
    if region in ['home-cam', 'test']:
        loc_a = np.array([[0 // scale1, 50 // scale2],
                          [1280 // scale1, 50// scale2],
                          [1280 // scale1, 720 // scale2],
                          [0 // scale1, 720 // scale2]])
        motion_roi = [loc_a]
        motion_mask_names = ["A"]
    else:
        print(f"This region {region} is not supported.")
        os._exit(1)
    if motion_roi is not None:
        motion_regions = len(motion_mask_names)
        motion_roi = [region.astype(int) for region in motion_roi]
        path = [mplPath.Path(loc, closed=True) for loc in motion_roi]
        motion_roi_points = []
        for loc in motion_roi:
            mask = np.zeros((frame_height, frame_width))
            mask = cv2.fillConvexPoly(mask, loc, True) == 0
            motion_roi_points.append(
                list(zip(np.where(mask == 0)[1], np.where(mask == 0)[0]))
            )
        mpa = [np.array(roi_points) for roi_points in motion_roi_points]

    return motion_mask_names, motion_regions, motion_roi, mpa, path


def select_region_ip(region):
    ip = ""
    return ip


def get_screenshot(region):
    ip = select_region_ip(region)
    cap = cv2.VideoCapture(ip)
    ret, img = cap.read()
    cv2.imwrite(
        region[0]
        + "_screenshot_"
        + time.strftime("%Y-%m-%dT%H%M%S", time.localtime())
        + ".png",
        img,
    )
    return img


def draw_roi(region):
    img = get_screenshot(region)
    height, width = img.shape[:2]
    mm_names, _, motion_roi, _, _ = set_region_roi(region, width, height)
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255)]
    font = cv2.FONT_HERSHEY_SIMPLEX
    if motion_roi is not None:
        for idx, region in enumerate(motion_roi):
            cv2.drawContours(img, [region], -1, colors[idx], 2)
            cv2.putText(
                img,
                mm_names[idx],
                (np.min(region[:, 0]), np.max(region[:, 1])),
                font,
                1,
                colors[idx],
                3,
            )

    cv2.imwrite(region[0] + "_roi.png", img)


def terminal_video(region):
    ip = select_region_ip(region)
    cap = cv2.VideoCapture(ip)
    ret, img = cap.read()
    height, width = img.shape[:2]
    aspect_ratio = height / width
    new_width = 120
    new_height = aspect_ratio * new_width * 0.55
    while ret:
        try:
            ret, img = cap.read()
            img = cv2.resize(img, (int(new_width), int(new_height)))
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) // 25
            # pixels = img.flatten()
            chars = ["B", "S", "#", "&", "@", "$", "%", "*", "!", ":", "."]
            ai = [
                chars[img[m, n]]
                for m in range(img.shape[0])
                for n in range(img.shape[1])
            ]
            ai = "".join(ai)
            new_pixels_count = len(ai)
            ascii_image = [
                ai[index : index + new_width]
                for index in range(0, new_pixels_count, new_width)
            ]
            ascii_image = "\n".join(ascii_image)
            os.system("clear")
            print(ascii_image)
        except KeyboardInterrupt:
            cap.release()
            cv2.destroyAllWindows()
            sys.exit()
