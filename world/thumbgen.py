"""The thumbnail really is generated from the creative brief - the same
nano-banana pipeline as the lab's own hero art. Falls back to a prebaked
thumb (honestly flagged) if the image model is unavailable."""
import pathlib
import shutil

from agent import config

THUMBS = config.ROOT / "app" / "static" / "thumbs"
FALLBACK = config.ROOT / "app" / "static" / "art" / "thumb-chores.png"

STYLE_WORDS = {
    "low-poly": ("cozy low-poly faceted 3D art, Monument Valley register, warm "
                 "pastel palette, soft bright daylight, handmade miniature diorama"),
    "paper": "layered paper-craft cutout art, soft shadows, warm pastel paper textures",
    "bright": "bold flat vector illustration, bright cheerful colors, clean shapes",
}


def generate(run_id: str, title: str, choices: dict) -> dict:
    """Returns {"ref": "/static/thumbs/<run>.png", "generated": bool}."""
    THUMBS.mkdir(parents=True, exist_ok=True)
    out = THUMBS / f"{run_id}.png"
    style = STYLE_WORDS.get(choices.get("style", ""), STYLE_WORDS["low-poly"])
    prompt = (f"{style}. YouTube thumbnail illustration, no text, no words, no "
              f"letters. Scene: {choices.get('character', 'a tiny robot')} — "
              f"{choices.get('subject', title)} — one comic decisive moment, "
              f"expressive, joyful disaster energy, generous negative space.")
    try:
        from google import genai
        from google.genai.types import GenerateContentConfig, ImageConfig
        client = genai.Client()   # env decides: Vertex (ADC) or AI Studio key
        r = client.models.generate_content(
            model="gemini-3-pro-image", contents=prompt,
            config=GenerateContentConfig(response_modalities=["TEXT", "IMAGE"],
                                         image_config=ImageConfig(aspect_ratio="16:9")))
        for part in r.candidates[0].content.parts:
            data = getattr(getattr(part, "inline_data", None), "data", None)
            if data:
                out.write_bytes(data)
                return {"ref": f"/static/thumbs/{out.name}", "generated": True}
        raise RuntimeError("no image part in response")
    except Exception as e:
        print(f"  [thumbgen] fell back to prebaked ({str(e)[:70]})")
        shutil.copyfile(FALLBACK, out)
        return {"ref": f"/static/thumbs/{out.name}", "generated": False}
