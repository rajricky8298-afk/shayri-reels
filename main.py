
"""
Hindi Shorts / Reels Video Generator
------------------------------------
Creates a vertical 9:16 video from:
- AI-generated images using Gemini
- Hindi AI narration using Gemini TTS
- Hindi captions
- H.264 video + AAC audio in an MP4 container

Required environment variable:
    GEMINI_API_KEY

Run:
    python main.py

Change the SCENES below to make a different video.
"""

import base64
import os
import subprocess
import textwrap
from pathlib import Path

from google import genai
from PIL import Image, ImageDraw, ImageFont

# -------------------- SETTINGS --------------------

IMAGE_MODEL = "gemini-3.1-flash-image"
VOICE_MODEL = "gemini-3.8-flash-tts"
VOICE_NAME = "Kore"

WIDTH = 1080
HEIGHT = 1920
FPS = 30

OUTPUT_DIR = Path("output")
WORK_DIR = OUTPUT_DIR / "work"
FINAL_VIDEO = OUTPUT_DIR / "hindi_short.mp4"

# Change these scenes to create a different Short.
# Each scene has its own narration, image prompt and Hindi caption.
SCENES = [
    {
        "narration": (
            "क्या आप जानते हैं कि मोना लिसा की मुस्कान "
            "आज भी दुनिया के सबसे बड़े रहस्यों में से एक है?"
        ),
        "caption": "मोना लिसा की रहस्यमयी मुस्कान",
        "image_prompt": (
            "Vertical 9:16 cinematic documentary image of the "
            "Mona Lisa painting inside a historic art museum, "
            "mysterious atmosphere, realistic oil painting, "
            "dramatic soft lighting, highly detailed, no text, "
            "no letters, no watermark."
        ),
    },
    {
        "narration": (
            "इस मशहूर पेंटिंग को लियोनार्डो दा विंची ने "
            "पुनर्जागरण काल में बनाया था।"
        ),
        "caption": "लियोनार्डो दा विंची की उत्कृष्ट कृति",
        "image_prompt": (
            "Vertical 9:16 cinematic historical scene of "
            "Leonardo da Vinci working in a Renaissance-era "
            "Florentine studio, old notebooks, brushes and "
            "paintings, historically inspired, warm candlelight, "
            "realistic documentary photography, no text, no watermark."
        ),
    },
    {
        "narration": (
            "लेकिन सबसे हैरान करने वाली बात यह है कि "
            "उसकी मुस्कान कभी साफ दिखाई देती है और कभी गायब लगती है।"
        ),
        "caption": "क्या उसकी मुस्कान बदलती है?",
        "image_prompt": (
            "Vertical 9:16 extreme close-up of the Mona Lisa's "
            "face and subtle smile, soft shadows, mysterious "
            "museum lighting, detailed Renaissance oil painting, "
            "cinematic composition, no text, no watermark."
        ),
    },
    {
        "narration": (
            "इसका एक कारण है लियोनार्डो की खास तकनीक, "
            "जिसमें रोशनी और छाया धीरे-धीरे एक-दूसरे में घुलती हैं।"
        ),
        "caption": "रोशनी और छाया का जादू",
        "image_prompt": (
            "Vertical 9:16 close-up artistic study of a Renaissance "
            "portrait showing subtle transitions between light and "
            "shadow, layered oil paint texture, museum-quality art, "
            "cinematic soft lighting, no text, no watermark."
        ),
    },
    {
        "narration": (
            "शायद यही वजह है कि पाँच सौ साल बाद भी "
            "लोग उसकी मुस्कान का रहस्य खोज रहे हैं।"
        ),
        "caption": "रहस्य आज भी कायम है",
        "image_prompt": (
            "Vertical 9:16 cinematic view of the Mona Lisa painting "
            "behind protective museum glass, visitors softly blurred "
            "in the background, mysterious and elegant atmosphere, "
            "realistic documentary style, no text, no watermark."
        ),
    },
]

# -------------------- HELPERS --------------------


def run_command(command):
    """Run a system command and show useful errors."""
    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"Required program not found: {command[0]}. "
            "Install FFmpeg and ensure it is on PATH."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"Command failed: {' '.join(command)}\n"
            f"{exc.stderr[-3000:]}"
        ) from exc


def get_audio_duration(audio_path):
    """Read audio duration using FFprobe."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def get_hindi_font(size):
    """Find a Devanagari-capable font."""
    candidates = [
        os.getenv("HINDI_FONT", ""),
        "/usr/share/fonts/truetype/noto/"
        "NotoSansDevanagari-Regular.ttf",
        "/usr/share/fonts/truetype/noto/"
        "NotoSansDevanagariUI-Regular.ttf",
        "C:/Windows/Fonts/Nirmala.ttf",
        "C:/Windows/Fonts/mangal.ttf",
    ]

    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return ImageFont.truetype(candidate, size)

    raise FileNotFoundError(
        "Hindi font not found. Install Noto Sans Devanagari "
        "or set HINDI_FONT to the font's full file path."
    )


def wrap_caption(text, width=22):
    """Wrap Hindi text into short caption lines."""
    return "\n".join(textwrap.wrap(text, width=width))


def add_caption(image_path, caption):
    """Draw a readable Hindi caption over an AI image."""
    image = Image.open(image_path).convert("RGB")
    image = image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)

    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = get_hindi_font(56)

    caption_text = wrap_caption(caption)
    box = draw.multiline_textbbox(
        (0, 0),
        caption_text,
        font=font,
        spacing=16,
        align="center",
        stroke_width=0,
    )

    text_width = box[2] - box[0]
    text_height = box[3] - box[1]

    padding_x = 36
    padding_y = 28

    x1 = (WIDTH - text_width) // 2 - padding_x
    y1 = HEIGHT - text_height - 190 - padding_y
    x2 = (WIDTH + text_width) // 2 + padding_x
    y2 = HEIGHT - 190 + padding_y

    draw.rounded_rectangle(
        (x1, y1, x2, y2),
        radius=24,
        fill=(0, 0, 0, 175),
    )

    draw.multiline_text(
        ((WIDTH - text_width) // 2, y1 + padding_y - box[1]),
        caption_text,
        font=font,
        fill=(255, 255, 255, 255),
        spacing=16,
        align="center",
        stroke_width=1,
        stroke_fill=(0, 0, 0, 255),
    )

    Image.alpha_composite(overlay, image.convert("RGBA")).convert(
        "RGB"
    ).save(image_path, quality=95)


def generate_image(client, prompt, output_path):
    """Generate one vertical image using Gemini."""
    response = client.interactions.create(
        model=IMAGE_MODEL,
        input=prompt,
        response_format={
            "type": "image",
            "mime_type": "image/jpeg",
            "aspect_ratio": "9:16",
            "image_size": "1K",
        },
    )

    image_data = getattr(response.output_image, "data", None)
    if not image_data:
        raise RuntimeError(
            "Gemini returned no image. Check the API key, model "
            "availability and API response."
        )

    output_path.write_bytes(base64.b64decode(image_data))
    add_caption(output_path, prompt_caption(prompt))


def prompt_caption(prompt):
    """Unused fallback helper; captions are added in main()."""
    return ""


def generate_voice(client, narration, output_path):
    """Generate Hindi speech and save the returned WAV audio."""
    response = client.interactions.create(
        model=VOICE_MODEL,
        input=[
            {
                "type": "user_input",
                "content": [
                    {
                        "type": "text",
                        "text": narration,
                        "annotations": [
                            {
                                "type": "speech_metadata",
                                "style": (
                                    "Natural Hindi narration, clear "
                                    "Indian Hindi pronunciation, "
                                    "engaging documentary voice, "
                                    "moderate pace."
                                ),
                            }
                        ],
                    }
                ],
            }
        ],
        response_format={"type": "audio"},
        generation_config={
            "speech_config": [{"voice": VOICE_NAME}]
        },
    )

    audio_data = getattr(response.output_audio, "data", None)
    if not audio_data:
        raise RuntimeError(
            "Gemini returned no audio. Check TTS model availability "
            "and your API access."
        )

    output_path.write_bytes(base64.b64decode(audio_data))


def make_scene_clip(image_path, audio_path, clip_path):
    """Create a scene clip with H.264 video and AAC audio."""
    duration = get_audio_duration(audio_path)

    run_command(
        [
            "ffmpeg",
            "-y",
            "-loop", "1",
            "-framerate", str(FPS),
            "-i", str(image_path),
            "-i", str(audio_path),
            "-t", f"{duration:.3f}",
            "-vf",
            (
                f"scale={WIDTH}:{HEIGHT}:"
                "force_original_aspect_ratio=increase,"
                f"crop={WIDTH}:{HEIGHT},"
                f"fps={FPS},format=yuv420p"
            ),
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "44100",
            "-ac", "2",
            "-shortest",
            "-movflags", "+faststart",
            str(clip_path),
        ]
    )


def combine_clips(clip_paths):
    """Join all scene clips into the final MP4."""
    concat_file = WORK_DIR / "clips.txt"

    with concat_file.open("w", encoding="utf-8") as file:
        for clip in clip_paths:
            # The generated filenames contain no apostrophes.
            file.write(f"file '{clip.resolve().as_posix()}'\n")

    run_command(
        [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "44100",
            "-ac", "2",
            "-movflags", "+faststart",
            str(FINAL_VIDEO),
        ]
    )


# -------------------- MAIN PROGRAM --------------------


def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is missing. Add it to your environment "
            "or GitHub Actions secrets."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    client = genai.Client(api_key=api_key)
    clip_paths = []

    print(f"Generating {len(SCENES)} scenes...")

    for index, scene in enumerate(SCENES, start=1):
        print(f"\nScene {index}/{len(SCENES)}")

        image_path = WORK_DIR / f"scene_{index:02d}.jpg"
        audio_path = WORK_DIR / f"scene_{index:02d}.wav"
        clip_path = WORK_DIR / f"clip_{index:02d}.mp4"

        print("Generating AI image...")
        response = client.interactions.create(
            model=IMAGE_MODEL,
            input=scene["image_prompt"],
            response_format={
                "type": "image",
                "mime_type": "image/jpeg",
                "aspect_ratio": "9:16",
                "image_size": "1K",
            },
        )

        image_data = getattr(response.output_image, "data", None)
        if not image_data:
            raise RuntimeError(
                f"No image returned for scene {index}."
            )

        image_path.write_bytes(base64.b64decode(image_data))
        add_caption(image_path, scene["caption"])

        print("Generating Hindi narration...")
        generate_voice(client, scene["narration"], audio_path)

        print("Building scene clip...")
        make_scene_clip(image_path, audio_path, clip_path)
        clip_paths.append(clip_path)

    print("\nCombining clips...")
    combine_clips(clip_paths)

    print("\nVideo generated successfully!")
    print(f"Output file: {FINAL_VIDEO.resolve()}")
    print("Format: MP4 / H.264 video / AAC audio")
    print("Resolution: 1080 x 1920 (vertical 9:16)")


if __name__ == "__main__":
    main()
