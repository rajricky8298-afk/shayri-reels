
import os
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone

import requests
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parent
OUTPUT = ROOT / "output"
OUTPUT.mkdir(exist_ok=True)

VIDEO = OUTPUT / "shayari_reel.mp4"
MUSIC = ROOT / "assets" / "music.mp3"
POST = OUTPUT / "post.json"

API_URL = (
    "https://generativelanguage.googleapis.com/"
    "v1beta/models/gemini-3.8-flash:generateContent"
)

def generate_shayari():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY secret is missing.")

    prompt = """
    Write one original Hindi shayari in Devanagari.
    Theme: love, life, hope, or self-respect.
    Exactly four short lines. Do not copy famous poetry
    or song lyrics.

    Return only JSON in this format:
    {
      "title": "short Hindi title",
      "shayari": "line one\\nline two\\nline three\\nline four",
      "caption": "short Hindi caption",
      "hashtags": ["#HindiShayari", "#Shayari"]
    }
    """

    response = requests.post(
        API_URL,
        headers={"x-goog-api-key": key},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json"
            },
        },
        timeout=180,
    )

    if response.status_code != 200:
        print("Gemini API error:", response.status_code, response.text)

    response.raise_for_status()
    result = response.json()

    raw = result["candidates"][0]["content"]["parts"][0]["text"]
    data = json.loads(raw)

    for field in ("title", "shayari", "caption", "hashtags"):
        if field not in data:
            raise ValueError(f"AI response is missing {field}")

    return data

def find_font():
    candidates = [
        "/usr/share/fonts/truetype/noto/"
        "NotoSansDevanagari-Regular.ttf",
        "/usr/share/fonts/truetype/noto/"
        "NotoSansDevanagariUI-Regular.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return path
    raise FileNotFoundError("Hindi Devanagari font not found.")

def create_background():
    width, height = 720, 1280
    image = Image.new("RGB", (width, height))
    pixels = image.load()

    for y in range(height):
        for x in range(width):
            glow = max(0, 1 - abs(x - width / 2) / 500)
            pixels[x, y] = (
                int(12 + 12 * glow),
                int(15 + 18 * y / height),
                int(38 + 50 * glow),
            )

    return image

def create_video(data):
    if not MUSIC.exists():
        raise FileNotFoundError(
            "Music missing: upload assets/music.mp3"
        )

    font_path = find_font()
    image = create_background()
    draw = ImageDraw.Draw(image)

    title_font = ImageFont.truetype(font_path, 32)
    poem_font = ImageFont.truetype(font_path, 40)
    footer_font = ImageFont.truetype(font_path, 24)

    draw.text(
        (360, 245), data["title"],
        font=title_font, fill=(255, 215, 150), anchor="mm"
    )

    # Split at word boundaries and keep lines within the frame.
    words = data["shayari"].replace("\n", " ").split()
    lines = []
    current = ""

    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=poem_font)[2] <= 620:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    lines = lines[:8]
    line_height = 78
    start_y = (640 - len(lines) * line_height / 2)

    for index, line in enumerate(lines):
        draw.text(
            (360, int(start_y + index * line_height)),
            line,
            font=poem_font,
            fill="white",
            anchor="mm",
            stroke_width=1,
            stroke_fill=(10, 10, 25),
        )

    draw.text(
        (360, 1080), "दिल से महसूस करें",
        font=footer_font, fill=(255, 215, 150), anchor="mm"
    )

    still = OUTPUT / "background.jpg"
    image.save(still, quality=95)

    subprocess.run([
        "ffmpeg", "-y",
        "-loop", "1", "-framerate", "24", "-i", str(still),
        "-stream_loop", "-1", "-i", str(MUSIC),
        "-t", "20",
        "-vf", "scale=720:1280,fps=24,format=yuv420p",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest", "-movflags", "+faststart",
        str(VIDEO),
    ], check=True)

def main():
    data = generate_shayari()
    create_video(data)

    data["date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    POST.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("Created:", VIDEO)

if __name__ == "__main__":
    main()
