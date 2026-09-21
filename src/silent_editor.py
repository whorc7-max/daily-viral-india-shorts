import os
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


TARGET_W, TARGET_H = 1080, 1920
FONT_DIR = "/usr/share/fonts/truetype/noto"


def _font(name: str, size: int):
    candidates = [
        os.path.join(FONT_DIR, name),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _phrases(script: str) -> list[str]:
    parts = re.split(r"(?<=[।.!?])\s+", script.strip())
    result = []
    for part in parts:
        words = part.strip().split()
        if not words:
            continue
        while len(words) > 10:
            result.append(" ".join(words[:10]))
            words = words[10:]
        result.append(" ".join(words))
    return result or ["Daily Viral India"]


def _background(index: int) -> Image.Image:
    palettes = [
        ((19, 32, 67), (107, 35, 142)),
        ((7, 68, 74), (13, 132, 119)),
        ((87, 28, 47), (204, 75, 100)),
        ((41, 35, 92), (38, 108, 176)),
    ]
    start, end = palettes[index % len(palettes)]
    image = Image.new("RGB", (TARGET_W, TARGET_H))
    pixels = image.load()
    for y in range(TARGET_H):
        ratio = y / max(1, TARGET_H - 1)
        color = tuple(int(start[i] * (1 - ratio) + end[i] * ratio) for i in range(3))
        for x in range(TARGET_W):
            pixels[x, y] = color
    return image


def _fit_image(path: str, index: int) -> Image.Image:
    try:
        image = Image.open(path).convert("RGB")
        image = ImageOps.fit(image, (TARGET_W, TARGET_H), method=Image.Resampling.LANCZOS)
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 95))
        return Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    except Exception as exc:
        print(f"  Could not use image {path}: {exc}")
        return _background(index)


def _draw_wrapped(draw, text, font, max_width):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


class SilentVideoEditor:
    def __init__(self, workdir: str | None = None):
        self.workdir = workdir or tempfile.mkdtemp(prefix="silent_short_")

    def compose(
        self,
        image_paths: list[str],
        script: str,
        output_path: str,
        target_duration: float = 55,
    ) -> str:
        phrases = _phrases(script)
        weights = [max(1, len(phrase.split())) for phrase in phrases]
        total_weight = sum(weights)
        durations = [target_duration * weight / total_weight for weight in weights]
        slides_dir = os.path.join(self.workdir, "slides")
        os.makedirs(slides_dir, exist_ok=True)
        manifest = os.path.join(self.workdir, "slides.txt")
        caption_font = _font("NotoSansDevanagari-Bold.ttf", 62)
        label_font = _font("NotoSansDevanagari-Bold.ttf", 34)
        images = image_paths or []
        slide_paths = []

        for index, (phrase, duration) in enumerate(zip(phrases, durations)):
            base = _fit_image(images[index % len(images)], index) if images else _background(index)
            draw = ImageDraw.Draw(base, "RGBA")
            draw.rounded_rectangle((55, 70, TARGET_W - 55, 150), radius=28, fill=(0, 0, 0, 130))
            draw.text((85, 91), "DAILY VIRAL INDIA", font=label_font, fill=(255, 255, 255, 245))

            box_left, box_top, box_right, box_bottom = 55, 1240, TARGET_W - 55, 1765
            draw.rounded_rectangle(
                (box_left, box_top, box_right, box_bottom),
                radius=38,
                fill=(0, 0, 0, 175),
                outline=(255, 255, 255, 120),
                width=3,
            )
            lines = _draw_wrapped(draw, phrase, caption_font, box_right - box_left - 100)
            line_height = 84
            text_height = len(lines) * line_height
            y = box_top + ((box_bottom - box_top - text_height) // 2)
            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=caption_font)
                x = (TARGET_W - (bbox[2] - bbox[0])) // 2
                draw.text((x, y), line, font=caption_font, fill=(255, 255, 255, 255))
                y += line_height

            progress = int((index + 1) / len(phrases) * (TARGET_W - 110))
            draw.rounded_rectangle((55, 1835, TARGET_W - 55, 1850), radius=7, fill=(255, 255, 255, 70))
            draw.rounded_rectangle((55, 1835, 55 + progress, 1850), radius=7, fill=(255, 213, 79, 255))

            slide_path = os.path.join(slides_dir, f"slide_{index:03d}.png")
            base.save(slide_path, format="PNG", optimize=True)
            slide_paths.append((slide_path, duration))

        with open(manifest, "w", encoding="utf-8") as file:
            for path, duration in slide_paths:
                file.write(f"file '{Path(path).as_posix()}'\n")
                file.write(f"duration {duration:.3f}\n")
            file.write(f"file '{Path(slide_paths[-1][0]).as_posix()}'\n")

        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", manifest,
                "-t", f"{target_duration:.3f}", "-r", "30", "-an",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                output_path,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        return output_path
