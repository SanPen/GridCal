import numpy as np
import cv2

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("Cannot open camera")
    exit()

video = None

while True:
    # Capture frame-by-frame
    ret, frame = cap.read()

    if video is None:
        height, width = frame.shape[:2]
        video = cv2.VideoWriter(filename="cam.mp4",
                                fourcc=cv2.VideoWriter_fourcc(*'mp4v'),
                                fps=30,
                                frameSize=(width, height))

    # if frame is read correctly ret is True
    if not ret:
        print("Can't receive frame (stream end?). Exiting ...")
        break

    video.write(frame)

    # Our operations on the frame come here
    frame2 = cv2.cvtColor(frame, cv2.COLOR_RGB2RGBA)
    # Display the resulting frame
    cv2.imshow('frame', frame2)
    if cv2.waitKey(1) == ord('q'):
        break

# When everything done, release the capture
cap.release()
video.release()
cv2.destroyAllWindows()
