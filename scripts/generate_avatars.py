"""Generate avatar images using OpenAI gpt-image-1 (DALL-E) API."""

import base64
import os
import sys
from pathlib import Path

from openai import OpenAI

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "apps" / "backend" / "static" / "models" / "avatars"

PROMPTS = {
    "chibi-chef": (
        "A cute chibi chef character, kawaii style, wearing white chef hat and apron, "
        "holding a wooden spoon, simple design, low poly, game asset style, "
        "clean white background, soft pastel colors, single character centered, "
        "icon style, no text"
    ),
    "female-chef": (
        "A friendly female chef figurine, cartoon style, wearing chef uniform with "
        "orange apron, short hair, smiling, holding a frying pan, miniature figure, "
        "3D icon style, warm colors, clean white background, single character centered, "
        "no text"
    ),
    "cooking-pot": (
        "A cute cartoon cooking pot with lid, slightly tilted, steam coming out, "
        "warm orange and cream colors, 3D icon style, rounded edges, miniature, "
        "clean white background, centered, no text"
    ),
}


def main():
    api_key = os.environ.get("EMBEDDING_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: No OpenAI API key found (EMBEDDING_API_KEY or OPENAI_API_KEY)")
        sys.exit(1)

    client = OpenAI(api_key=api_key)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for name, prompt in PROMPTS.items():
        out_path = OUTPUT_DIR / f"{name}.png"
        if out_path.exists():
            print(f"SKIP: {out_path} already exists")
            continue

        print(f"Generating {name}...")
        try:
            result = client.images.generate(
                model="gpt-image-1",
                prompt=prompt,
                n=1,
                size="1024x1024",
                quality="medium",
            )

            # gpt-image-1 returns base64 by default
            image_b64 = result.data[0].b64_json
            if image_b64:
                image_bytes = base64.b64decode(image_b64)
                out_path.write_bytes(image_bytes)
                print(f"  -> Saved: {out_path} ({len(image_bytes)} bytes)")
            elif result.data[0].url:
                # fallback: download from URL
                import httpx
                resp = httpx.get(result.data[0].url)
                out_path.write_bytes(resp.content)
                print(f"  -> Saved: {out_path} ({len(resp.content)} bytes)")
            else:
                print(f"  -> ERROR: No image data returned for {name}")
        except Exception as e:
            print(f"  -> ERROR generating {name}: {e}")

    print("\nDone! Generated files:")
    for f in sorted(OUTPUT_DIR.glob("*.png")):
        print(f"  {f}")


if __name__ == "__main__":
    main()
