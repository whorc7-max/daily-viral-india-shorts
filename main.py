import os
import sys
import shutil
import tempfile
import traceback

from src.script_generator import ScriptGenerator
from src.downloader import VideoDownloader
from src.music_provider import MusicProvider
from src.silent_editor import SilentVideoEditor
from src.sound_designer import SoundDesigner
from src.uploader import YouTubeUploader
from src.voice_generator import VoiceGenerator


def cleanup(paths: list[str]):
    for p in paths:
        try:
            if os.path.isfile(p):
                os.remove(p)
            elif os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
        except Exception:
            pass


def main():
    workdir = tempfile.mkdtemp(prefix="yt_shorts_")
    temp_files = [workdir]

    try:
        print("=" * 50)
        print("YouTube Shorts Automation Pipeline")
        print("=" * 50)

        print("\n[1/8] Finding a current India trend and writing one Hindi Short...")
        content = ScriptGenerator().generate()
        print(f"  Title: {content['title']}")
        print(f"  Scenes: {len(content['visual_scenes'])}")

        print("\n[2/8] Generating Hindi voiceover...")
        voice_path = os.path.join(workdir, "voiceover.mp3")
        voice_duration = VoiceGenerator().generate(
            text=content["voiceover_script"],
            output_path=voice_path,
        )
        print(f"  Voice duration: {voice_duration:.1f}s")
        temp_files.append(voice_path)

        print("\n[3/8] Matching the topic to authorized music or a free CC0 track...")
        music_path = MusicProvider().download(
            keywords=content["visual_keywords"],
            output_dir=workdir,
            topic=content.get("title", ""),
        )
        if music_path:
            temp_files.append(music_path)
            music_manifest = os.path.join(workdir, "music_source.json")
            if os.path.isfile(music_manifest):
                shutil.copy2(music_manifest, os.path.join(os.getcwd(), "music_source.json"))
        else:
            print("  No licensed track found; continuing without background music")

        print("\n[4/8] Preparing a scene-matched background sound for each beat...")
        scene_audio_paths = SoundDesigner().download_scene_sounds(
            content.get("visual_scenes", []), workdir
        )
        available_ambience = sum(bool(path) for path in scene_audio_paths)
        print(f"  Prepared {available_ambience}/{len(scene_audio_paths)} scene ambience bed(s)")

        print("\n[5/8] Downloading topic-matched Pexels video clips first...")
        downloader = VideoDownloader()
        video_paths, image_paths = downloader.download_all(
            content["visual_scenes"],
            workdir,
            fallback_keywords=content["visual_keywords"],
            allow_image_fallback=True,
        )
        temp_files.extend(path for path in video_paths + image_paths if path)
        missing_clips = sum(path is None for path in video_paths)
        print(f"  Downloaded {len(video_paths) - missing_clips} real video clips")
        fallback_images = sum(
            video_path is None and image_path is not None
            for video_path, image_path in zip(video_paths, image_paths)
        )
        print(f"  Using {fallback_images} image fallback(s) where video was unavailable")

        print("\n[6/8] Rendering the video with voice, music, and scene ambience...")
        output_path = os.path.join(workdir, "final_short.mp4")
        editor = SilentVideoEditor(workdir)
        editor.compose(
            image_paths=image_paths,
            script=content["voiceover_script"],
            output_path=output_path,
            target_duration=voice_duration,
            voice_path=voice_path,
            music_path=music_path,
            clip_paths=video_paths,
            scene_specs=content["visual_scenes"],
            scene_audio_paths=scene_audio_paths,
        )
        temp_files.append(output_path)

        # Keep a copy outside the temporary directory so Actions can archive it
        # even when YouTube rejects the upload because of a channel limit.
        preserved_output = os.path.join(os.getcwd(), "final_short.mp4")
        shutil.copy2(output_path, preserved_output)
        print(f"  Video saved: {preserved_output}")

        print("\n[7/8] Uploading to YouTube...")
        uploader = YouTubeUploader()
        sources = content.get("source_urls", [])
        description = content["description"]
        if sources:
            description += "\n\nSources:\n" + "\n".join(sources)
        uploader.upload(
            video_path=output_path,
            title=content["title"],
            description=description,
            tags=content["tags"],
            visibility=os.environ.get("YT_PRIVACY_STATUS") or "public",
        )

        print("\n[8/8] Done! Short uploaded with voice, available licensed music, and scene ambience.")

    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
    finally:
        print("\nCleaning up temporary files...")
        cleanup(temp_files)


if __name__ == "__main__":
    main()
