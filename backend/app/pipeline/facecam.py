"""Find a streamer's face cam: the face that stays in the same spot across many frames.

Game characters' faces get detected too, but they move around between frames; the
webcam overlay doesn't. Returns a box in normalized coordinates {x, y, w, h} (0..1).
"""

import subprocess
from pathlib import Path

from app.ffmpeg import ffmpeg_bin


def grab_frame(src: str, at: float, out: Path, headers: str = "") -> Path | None:
    """One frame at `at` seconds (input-relative) from a local file or remote URL, 960 px wide."""
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y"]
    if headers:
        cmd += ["-headers", headers]
    cmd += ["-ss", f"{max(0.0, at):.2f}", "-i", src, "-frames:v", "1", "-vf", "scale=960:-2", "-q:v", "3", str(out)]
    r = subprocess.run(cmd, capture_output=True, check=False, timeout=120)
    return out if r.returncode == 0 and out.exists() else None


def _faces(img):
    import cv2

    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    gray = cv2.equalizeHist(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
    h, w = gray.shape
    found = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=6, minSize=(int(w * 0.03), int(w * 0.03)))
    return [((x + fw / 2) / w, (y + fh / 2) / h, fw / w, fh / h) for (x, y, fw, fh) in found]


def detect(frames: list[Path], frame_aspect: float = 16 / 9) -> dict | None:
    import cv2

    per_frame = []
    for f in frames:
        img = cv2.imread(str(f))
        if img is not None:
            per_frame.append(_faces(img))
    n = len(per_frame)
    if n < 3:
        return None

    # For every detected face, count how many frames have a face in (almost) the same place.
    best, best_count = None, 0
    for faces in per_frame:
        for cx, cy, fw, _fh in faces:
            matches = []
            for other in per_frame:
                m = [o for o in other if abs(o[0] - cx) < 0.04 and abs(o[1] - cy) < 0.05 and 0.6 < o[2] / fw < 1.6]
                if m:
                    matches.append(m[0])
            if len(matches) > best_count:
                best_count, best = len(matches), matches
    if not best or best_count < max(3, int(n * 0.4)):
        return None

    med = lambda i: sorted(m[i] for m in best)[len(best) // 2]  # noqa: E731
    cx, cy, fw = med(0), med(1), med(2)

    # Face -> webcam box: ~3.2 face-widths wide, 4:3, face a bit above the middle.
    box_w = min(1.0, fw * 3.2)
    box_h = min(1.0, box_w * frame_aspect * 0.75)
    x = min(max(0.0, cx - box_w / 2), 1.0 - box_w)
    y = min(max(0.0, cy - box_h * 0.45), 1.0 - box_h)
    return {"x": round(x, 4), "y": round(y, 4), "w": round(box_w, 4), "h": round(box_h, 4)}
