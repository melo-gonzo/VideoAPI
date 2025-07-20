import sys

sys.path.append("/usr/lib/python3/dist-packages")
import cv2

# Define a list to store the clicked points
clicked_points = []


# Define a callback function to capture mouse clicks
def mouse_callback(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONUP:
        # Append the clicked point to the list
        clicked_points.append((x, y))


# Open the video stream
cap = cv2.VideoCapture("rtsp://{username}:{password}@address")
ret, frame = cap.read()
og_frame = frame.copy()
cap.release()
# Get the width and height of the video stream
height, width, channels = frame.shape
# Calculate the padding size
# padding_w = int(0.1 * width)
# padding_h = int(0.1 * height)

# Define the padding size
padding = int(min(width, height) * 0.05)

# Define the desired window size
window_width = 800
window_height = 600

# Create a named window with the specified size
cv2.namedWindow("ROI", cv2.WINDOW_NORMAL)
cv2.resizeWindow("ROI", window_width, window_height)

while True:
    # Read a frame from the video stream
    if ret:
        # Create a black image for padding
        black = [0, 0, 255]
        padded_frame = cv2.copyMakeBorder(
            frame, padding, padding, padding, padding, cv2.BORDER_CONSTANT, value=black
        )
        # Set the mouse callback function for the padded frame
        cv2.setMouseCallback("ROI", mouse_callback)
        # Draw lines connecting all clicked points
        for i in range(len(clicked_points) - 1):
            cv2.line(
                padded_frame, clicked_points[i], clicked_points[i + 1], (0, 255, 0), 2
            )

        try:
            cv2.line(
                padded_frame, clicked_points[0], clicked_points[-1], (0, 255, 0), 2
            )
        except IndexError:
            pass

        cv2.imshow("ROI", padded_frame)
        # Show the original frame with lines connecting clicked points
        # Wait for a key press
        key = cv2.waitKey(1) & 0xFF
        # If the 'q' key is pressed, exit the loop
        if key == ord("q"):
            break

# Report the pixel locations of the clicked points in terms of the unpadded frame
cp = []
for i, point in enumerate(clicked_points):
    x, y = point
    x -= padding
    y -= padding
    x = max(0, x)
    y = max(0, y)
    x = min(x, width)
    y = min(y, height)
    print("Clicked point {}: ({}, {})".format(i + 1, x, y))
    cp.append((x, y))

for i, point in enumerate(cp):
    print(
        f"    [{point[0]} // scale1, {point[1]} // scale2]{',' if i < len(cp)-1 else ''}"
    )

print("])")

# Release the video stream and close all windows
cv2.destroyAllWindows()
