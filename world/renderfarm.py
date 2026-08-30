"""The final cut - a real, playable file.

The render farm in this lab is PREBAKED: world/broker.py hands back receipts
(`prebaked/shot_N.mp4`) on a deterministic clock, because the lesson is the
waiting, not the pixels. What IS real is the thumbnail the studio generates
from your brief - so post-production turns that image into a genuine
6-second H.264 and writes it where the app already serves static files.
That is the file that plays on your Channel wall.

No ffmpeg on the machine? Every function returns None, post-production falls
back to a plain text manifest, and the lab keeps working - you just get a
still card on the wall instead of a clip.
"""
import shutil
import subprocess

from agent import config

RENDERS = config.ROOT / "app" / "static" / "renders"
WEB = "/static/renders"


def final_cut(run_id: str, thumb_ref: str, seconds: int = 6) -> str | None:
    """thumbnail -> playable mp4. Returns the web path, or None."""
    ff = shutil.which("ffmpeg")
    if not ff or not thumb_ref:
        return None
    src = config.ROOT / "app" / thumb_ref.lstrip("/")
    if not src.exists():
        return None
    RENDERS.mkdir(parents=True, exist_ok=True)
    out = RENDERS / f"final_{run_id}.mp4"
    cmd = [ff, "-y", "-loop", "1", "-i", str(src),
           "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", str(seconds),
           "-vf", ("scale=1280:720:force_original_aspect_ratio=decrease,"
                   "pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=0xF5E9DA"),
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
           "-shortest", str(out)]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
    except Exception:
        return None
    return f"{WEB}/{out.name}" if out.exists() else None
