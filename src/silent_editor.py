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
    return [part.strip() for part in parts if part.strip()] or ["Daily Viral India"]


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


def _fit_image(path: str | None, index: int) -> Image.Image:
    if not path:
        return _background(index)
    try:
        image = Image.open(path).convert("RGB")
        image = ImageOps.fit(image, (TARGET_W, TARGET_H), method=Image.Resampling.LANCZOS)
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 95))
        return Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    except Exception as exc:
        print(f"  Could not use image {path}: {exc}")
        return _background(index)


def _caption_overlay(phrase: str, index: int, scene_count: int) -> Image.Image:
    overlay = Image.new("RGBA", (TARGET_W, TARGET_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")
    caption_font = _font("NotoSansDevanagari-Bold.ttf", 62)
    label_font = _font("NotoSansDevanagari-Bold.ttf", 34)

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

    progress = int((index + 1) / max(1, scene_count) * (TARGET_W - 110))
    draw.rounded_rectangle((55, 1835, TARGET_W - 55, 1850), radius=7, fill=(255, 255, 255, 70))
    draw.rounded_rectangle((55, 1835, 55 + progress, 1850), radius=7, fill=(255, 213, 79, 255))
    return overlay


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
        image_paths: list[str | None],
        script: str,
        output_path: str,
        target_duration: float = 55,
        voice_path: str | None = None,
        music_path: str | None = None,
        clip_paths: list[str | None] | None = None,
    ) -> str:
        phrases = _phrases(script)
        weights = [max(1, len(phrase.split())) for phrase in phrases]
        total_weight = sum(weights)
        durations = [target_duration * weight / total_weight for weight in weights]
        scenes_dir = os.path.join(self.workdir, "scenes")
        os.makedirs(scenes_dir, exist_ok=True)
        manifest = os.path.join(self.workdir, "scenes.txt")
        images = image_paths or []
        clips = clip_paths or []
        scene_paths = []

        for index, (phrase, duration) in enumerate(zip(phrases, durations)):
            overlay = _caption_overlay(phrase, index, len(phrases))
            overlay_path = os.path.join(scenes_dir, f"caption_{index:03d}.png")
            overlay.save(overlay_path, format="PNG", optimize=True)

            clip_path = clips[index] if index < len(clips) else None
            if clip_path and os.path.isfile(clip_path):
                background_path = clip_path
                background_is_video = True
            else:
                background = _fit_image(images[index], index) if index < len(images) else _background(index)
                background_path = os.path.join(scenes_dir, f"background_{index:03d}.png")
                background.save(background_path, format="PNG", optimize=True)
                background_is_video = False

            scene_path = os.path.join(scenes_dir, f"scene_{index:03d}.mp4")
            background_input = (
                ["-stream_loop", "-1", "-i", background_path]
                if background_is_video
                else ["-loop", "1", "-i", background_path]
            )
            subprocess.run(
                [
                    "ffmpeg", "-y", *background_input,
                    "-loop", "1", "-i", overlay_path,
                    "-filter_complex",
                    (
                        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
                        "crop=1080:1920,setsar=1,fps=30[bg];"
                        "[1:v]format=rgba[caption];"
                        "[bg][caption]overlay=0:0:format=auto,format=yuv420p[v]"
                    ),
                    "-map", "[v]", "-t", f"{duration:.3f}", "-an",
                    "-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", scene_path,
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
            scene_paths.append((scene_path, duration))

        with open(manifest, "w", encoding="utf-8") as file:
            for path, _duration in scene_paths:
                file.write(f"file '{Path(path).as_posix()}'\n")

        video_only_path = os.path.join(self.workdir, "video_only.mp4")
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", manifest,
                "-t", f"{target_duration:.3f}", "-r", "30", "-an",
                "-c", "copy", "-movflags", "+faststart",
                video_only_path,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )

        if not voice_path:
            os.replace(video_only_path, output_path)
            return output_path

        if music_path:
            audio_args = [
                "-i", voice_path,
                "-stream_loop", "-1", "-i", music_path,
                "-filter_complex",
                "[2:a]volume=0.10[music];[1:a][music]amix=inputs=2:duration=first:dropout_transition=2[aout]",
                "-map", "0:v:0", "-map", "[aout]",
            ]
        else:
            audio_args = ["-i", voice_path, "-map", "0:v:0", "-map", "1:a:0"]

        subprocess.run(
            [
                "ffmpeg", "-y", "-i", video_only_path, *audio_args,
                "-t", f"{target_duration:.3f}", "-c:v", "copy", "-c:a", "aac",
                "-shortest", "-movflags", "+faststart", output_path,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        os.remove(video_only_path)
        return output_path
