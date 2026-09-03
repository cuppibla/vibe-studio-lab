"""The final cut - a real, playable film.

Post-production stitches what the lap actually produced: a short title card
cut from the thumbnail you approved, then every shot the farm delivered
(real Veo clips when the farm is real; when it is the prebaked clock, the
receipts are only strings and the film is the title card alone). Everything
is normalised to one format first - 1280x720, 24 fps, H.264, stereo AAC -
so the pieces concatenate without re-encoding twice.

No ffmpeg on the machine? Every function returns None, post-production falls
back to a plain text manifest, and the lab keeps working - you just get a
still card on the wall instead of a clip.
"""
import json
import shutil
import subprocess
import tempfile

from agent import config

RENDERS = config.ROOT / "app" / "static" / "renders"
WEB = "/static/renders"
TITLE_CARD_S = 1.5
VF = ("scale=1280:720:force_original_aspect_ratio=decrease,"
      "pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=0xF5E9DA,fps=24,format=yuv420p")


def _ff() -> str | None:
    return shutil.which("ffmpeg")


def _has_audio(path) -> bool:
    probe = shutil.which("ffprobe")
    if not probe:
        return False
    r = subprocess.run([probe, "-v", "error", "-select_streams", "a", "-show_entries",
                        "stream=codec_type", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True)
    return "audio" in r.stdout


def duration_ms(web_or_path) -> int | None:
    probe = shutil.which("ffprobe")
    p = (config.ROOT / "app" / str(web_or_path).lstrip("/")
         if str(web_or_path).startswith("/") else config.ROOT / str(web_or_path))
    if not probe or not p.exists():
        return None
    r = subprocess.run([probe, "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    try:
        return int(float(r.stdout.strip()) * 1000)
    except ValueError:
        return None


def _norm_still(ff, src, out, seconds) -> bool:
    cmd = [ff, "-y", "-loop", "1", "-i", str(src),
           "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", str(seconds),
           "-vf", VF, "-c:v", "libx264", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-ar", "44100", "-ac", "2", "-shortest", str(out)]
    return subprocess.run(cmd, capture_output=True, timeout=120).returncode == 0


def _norm_clip(ff, src, out) -> bool:
    if _has_audio(src):
        cmd = [ff, "-y", "-i", str(src), "-vf", VF, "-c:v", "libx264", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-ar", "44100", "-ac", "2", str(out)]
    else:
        cmd = [ff, "-y", "-i", str(src), "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
               "-vf", VF, "-c:v", "libx264", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-ar", "44100", "-ac", "2", "-shortest", str(out)]
    return subprocess.run(cmd, capture_output=True, timeout=300).returncode == 0


def final_cut(run_id: str, thumb_ref: str, shot_urls: list[str] | None = None,
              seconds: int = 6) -> str | None:
    """title card (from the thumbnail) + every real shot -> final_<run>.mp4.
    Returns the web path, or None. With no real shots the card alone plays
    for `seconds`."""
    ff = _ff()
    if not ff or not thumb_ref:
        return None
    thumb = config.ROOT / "app" / thumb_ref.lstrip("/")
    if not thumb.exists():
        return None
    clips = [config.ROOT / "app" / u.lstrip("/") for u in (shot_urls or [])
             if u and u.startswith(WEB)]
    clips = [c for c in clips if c.exists()]
    RENDERS.mkdir(parents=True, exist_ok=True)
    out = RENDERS / f"final_{run_id}.mp4"
    with tempfile.TemporaryDirectory() as td:
        pieces = []
        card = f"{td}/00_card.mp4"
        if not _norm_still(ff, thumb, card, TITLE_CARD_S if clips else seconds):
            return None
        pieces.append(card)
        for i, c in enumerate(clips, 1):
            piece = f"{td}/{i:02d}_shot.mp4"
            if _norm_clip(ff, c, piece):
                pieces.append(piece)
            else:
                print(f"  [postprod] could not normalise {c.name} - skipped")
        if len(pieces) == 1:                          # no usable shots: the card alone
            shutil.copyfile(card, out)
        else:
            lst = f"{td}/list.txt"
            with open(lst, "w") as f:
                for p in pieces:
                    f.write(f"file '{p}'\n")
            r = subprocess.run([ff, "-y", "-f", "concat", "-safe", "0", "-i", lst,
                                "-c", "copy", str(out)], capture_output=True, timeout=300)
            if r.returncode != 0:
                return None
    print(f"  [postprod] final cut: {len(pieces) - 1} shot(s) + title card -> {out.name}")
    return f"{WEB}/{out.name}" if out.exists() else None
