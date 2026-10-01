import os
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageOps


TARGET_W, TARGET_H = 1080, 1920


def _phrases(script: str, scene_specs: list[dict] | None = None) -> list[str]:
    if scene_specs:
        beats = [
            str(
                scene.get("voiceover_text")
                or scene.get("narration")
                or scene.get("text")
                or ""
            ).strip()
            for scene in scene_specs
            if isinstance(scene, dict)
        ]
        beats = [beat for beat in beats if beat]
        if beats and sum(len(beat.split()) for beat in beats) >= max(
            1, int(len(script.split()) * 0.9)
        ):
            return beats

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
        return ImageOps.fit(image, (TARGET_W, TARGET_H), method=Image.Resampling.LANCZOS)
    except Exception as exc:
        print(f"  Could not use image {path}: {exc}")
        return _background(index)


def _build_audio_filter(
    music_input_index: int | None,
    scene_inputs: list[tuple[int, float, float]],
) -> str:
    filters = ["[1:a]volume=1.0[voice]"]
    mix_labels = ["[voice]"]

    if music_input_index is not None:
        filters.append(f"[{music_input_index}:a]volume=0.18[music]")
        mix_labels.append("[music]")

    for index, (input_index, start, duration) in enumerate(scene_inputs):
        fade = min(0.6, duration / 2)
        fade_out_start = max(0, duration - fade)
        delay_ms = max(0, round(start * 1000))
        filters.append(
            f"[{input_index}:a]atrim=duration={duration:.3f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d={fade:.3f},"
            f"afade=t=out:st={fade_out_start:.3f}:d={fade:.3f},"
            f"volume=0.18,adelay=delays={delay_ms}:all=1[scene_{index}]"
        )
        mix_labels.append(f"[scene_{index}]")

    if len(mix_labels) == 1:
        filters.append("[voice]alimiter=limit=0.95[aout]")
    else:
        filters.append(
            f"{''.join(mix_labels)}amix=inputs={len(mix_labels)}:duration=first:"
            "dropout_transition=2:normalize=0,alimiter=limit=0.95[aout]"
        )
    return ";".join(filters)


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
        scene_specs: list[dict] | None = None,
        scene_audio_paths: list[str | None] | None = None,
    ) -> str:
        phrases = _phrases(script, scene_specs)
        print(f"  Rendering {len(phrases)} narration-aligned visual beat(s)")
        weights = [max(1, len(phrase.split())) for phrase in phrases]
        total_weight = sum(weights)
        durations = [target_duration * weight / total_weight for weight in weights]
        scenes_dir = os.path.join(self.workdir, "scenes")
        os.makedirs(scenes_dir, exist_ok=True)
        manifest = os.path.join(self.workdir, "scenes.txt")
        images = image_paths or []
        clips = clip_paths or []
        scene_paths = []

        for index, duration in enumerate(durations):
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
                    "-filter_complex",
                    (
                        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
                        "crop=1080:1920,setsar=1,fps=30,format=yuv420p[v]"
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

        audio_args = ["-i", voice_path]
        music_input_index = None
        next_audio_input = 2
        if music_path and os.path.isfile(music_path):
            music_input_index = next_audio_input
            audio_args.extend(["-stream_loop", "-1", "-i", music_path])
            next_audio_input += 1

        scene_inputs = []
        scene_start = 0.0
        for index, duration in enumerate(durations):
            sound_path = (
                scene_audio_paths[index]
                if scene_audio_paths and index < len(scene_audio_paths)
                else None
            )
            if sound_path and os.path.isfile(sound_path):
                audio_args.extend(["-stream_loop", "-1", "-i", sound_path])
                scene_inputs.append((next_audio_input, scene_start, duration))
                next_audio_input += 1
            scene_start += duration

        if music_input_index is not None or scene_inputs:
            audio_args.extend([
                "-filter_complex", _build_audio_filter(music_input_index, scene_inputs),
                "-map", "0:v:0", "-map", "[aout]",
            ])
            print(
                f"  Mixing continuous music and {len(scene_inputs)} scene ambience bed(s)"
                if music_input_index is not None
                else f"  Mixing {len(scene_inputs)} scene ambience bed(s)"
            )
        else:
            audio_args.extend(["-map", "0:v:0", "-map", "1:a:0"])

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
