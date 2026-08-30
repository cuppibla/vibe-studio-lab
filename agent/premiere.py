"""`python -m agent.premiere` - put your published video on the ROOM's platform.

The local Wall is your analytics engine; the room's VibeTube is where
everyone's videos meet. Same lesson as chapter 🏁, different host: publishing
is ONE multipart POST to a contract - no SDK, no session, just HTTP.

Needs (from your instructor, in .env):
  VIBETUBE_URL    the platform, e.g. https://<service>.run.app
  VIBETUBE_EVENT  the showroom code for this session
  VIBETUBE_NAME   how the room should credit you (optional)
"""
import os
import pathlib
import subprocess

import httpx

from . import config, state

URL = os.environ.get("VIBETUBE_URL", "").rstrip("/")
EVENT = os.environ.get("VIBETUBE_EVENT", "").strip()
NAME = os.environ.get("VIBETUBE_NAME", "").strip() or "Vibe Studio creator"


def package(st) -> pathlib.Path:
    """The prebaked farm gives us stand-in shots, so the premiere cut is the
    real generated THUMBNAIL as a 6-second poster video - a genuine H.264
    file the platform can transcode. (Swap in real Veo shots and this
    function is where your real final cut gets stitched.)"""
    out = config.RUNS / f"premiere_{st['run_id']}.mp4"
    if out.exists():
        return out
    thumb = (st.get("thumb") or {}).get("ref", "")
    thumb_file = config.ROOT / "app" / thumb.lstrip("/") if thumb else None
    if thumb_file and thumb_file.exists():
        src = ["-loop", "1", "-i", str(thumb_file)]
    else:  # honest fallback: a plain slate
        src = ["-f", "lavfi", "-i", "color=c=0xF5E9DA:s=1280x720"]
    cmd = ["ffmpeg", "-y", *src, "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
           "-t", "6", "-vf",
           "scale=1280:720:force_original_aspect_ratio=decrease,"
           "pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=white",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
           "-shortest", str(out)]
    subprocess.run(cmd, check=True, capture_output=True)
    return out


def main():
    if not URL or not EVENT:
        print("no room configured - set VIBETUBE_URL and VIBETUBE_EVENT in .env"
              "\n(your instructor has both; without a live event this step is"
              " optional - nothing later depends on it)")
        return
    st = state.load()
    pub = st.get("published")
    if not pub:
        print("nothing published yet - finish a lap first"); return

    print("── packaging the premiere cut (ffmpeg, ~5s) ──")
    cut = package(st)
    mins, secs = divmod(round(st.get("duration_ms", 6000) / 1000), 60)

    files = {"videoFile": (cut.name, cut.open("rb"), "video/mp4")}
    thumb = (st.get("thumb") or {}).get("ref", "")
    thumb_file = config.ROOT / "app" / thumb.lstrip("/") if thumb else None
    if thumb_file and thumb_file.exists():
        files["thumbnailFile"] = (thumb_file.name, thumb_file.open("rb"), "image/png")

    # YOUR avatar from chapter 2 rides along - the room sees the face you made
    from world import portrait
    mine = portrait.latest()
    av = config.ROOT / "app" / mine["url"].lstrip("/") if mine else None
    if av and av.exists():
        files["avatarFile"] = (av.name, av.open("rb"), "image/png")
        print(f"  attaching your avatar: {mine['url']}")

    print(f"── POST {URL}/api/events/{EVENT}/videos ──")
    r = httpx.post(
        f"{URL}/api/events/{EVENT}/videos",
        data={"title": st["script"]["title"],
              "description": st["script"]["description"],
              "duration": f"{mins}:{secs:02d}",
              "displayName": NAME,
              "projectId": pub["video_id"]},
        files=files, timeout=120)
    if r.status_code != 200:
        print(f"platform said {r.status_code}: {r.json().get('detail', r.text[:120])}")
        return
    vid = r.json()["id"]
    print("── the room can see you now ──")
    print(f"  watch it with everyone else: {URL}/e/{EVENT}?v={vid}")


if __name__ == "__main__":
    main()
