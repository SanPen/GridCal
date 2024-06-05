


import cv2  # provided by pip install opencv-python

def record_vides(fname = "mi_video.mp4", fps: int = 30):

    video = cv2.VideoWriter(fname, cv2.VideoWriter_fourcc(*'MP4V'), fps, (width, height))

    video.write(frame)

    video.release()
