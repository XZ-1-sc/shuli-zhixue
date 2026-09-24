from pathlib import Path
import cv2
import numpy as np

VIDEO = Path(r"D:\存放world，ppt,excell等等文件\智能体比赛\QQ20260921-122550.mp4")
OUT = Path(r"D:\「行测智脑」——基于多智能体协作的公考全科个性化导航系统\video_storyboard")
OUT.mkdir(parents=True, exist_ok=True)

cap = cv2.VideoCapture(str(VIDEO))
fps = cap.get(cv2.CAP_PROP_FPS)
frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
duration = frames / fps

thumbs = []
for sec in np.arange(0, duration, 5.0):
    cap.set(cv2.CAP_PROP_POS_MSEC, float(sec * 1000))
    ok, frame = cap.read()
    if not ok:
        continue
    h, w = frame.shape[:2]
    tw = 480
    th = round(h * tw / w)
    thumb = cv2.resize(frame, (tw, th), interpolation=cv2.INTER_AREA)
    label = f"{int(sec)//60:02d}:{int(sec)%60:02d}"
    cv2.rectangle(thumb, (0, 0), (92, 30), (0, 0, 0), -1)
    cv2.putText(thumb, label, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA)
    thumbs.append(thumb)
cap.release()

cols, rows = 4, 4
gap = 8
cell_h, cell_w = thumbs[0].shape[:2]
for page, start in enumerate(range(0, len(thumbs), cols * rows), 1):
    chunk = thumbs[start:start + cols * rows]
    sheet = np.full((rows * cell_h + (rows + 1) * gap, cols * cell_w + (cols + 1) * gap, 3), 238, np.uint8)
    for i, img in enumerate(chunk):
        r, c = divmod(i, cols)
        y = gap + r * (cell_h + gap)
        x = gap + c * (cell_w + gap)
        sheet[y:y + cell_h, x:x + cell_w] = img
    encoded = cv2.imencode(".jpg", sheet, [cv2.IMWRITE_JPEG_QUALITY, 88])[1]
    encoded.tofile(str(OUT / f"storyboard_{page:02d}.jpg"))

print(f"duration={duration:.3f}s thumbs={len(thumbs)} sheets={(len(thumbs)+15)//16} out={OUT}")
