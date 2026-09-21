import os
import sys
import shutil
import tempfile
import traceback

from src.script_generator import ScriptGenerator
from src.downloader import VideoDownloader
from src.music_provider import MusicProvider
from src.silent_editor import SilentVideoEditor
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

        print("\n[1/7] Finding a current India trend and writing one Hindi Short...")
        content = ScriptGenerator().generate()
        print(f"  Title: {content['title']}")
        print(f"  Scenes: {len(content['visual_scenes'])}")

        print("\n[2/7] Generating Hindi voiceover...")
        voice_path = os.path.join(workdir, "voiceover.mp3")
        voice_duration = VoiceGenerator().generate(
            text=content["voiceover_script"],
            output_path=voice_path,
        )
        print(f"  Voice duration: {voice_duration:.1f}s")
        temp_files.append(voice_path)

        print("\n[3/7] Downloading topic-matched royalty-free music...")
        music_path = MusicProvider().download(
            keywords=content["visual_keywords"],
            output_dir=workdir,
        )
        if music_path:
            temp_files.append(music_path)
        else:
            print("  Music unavailable; continuing with voice only")

        print("\n[4/7] Downloading optional licensed stock images...")
        downloader = VideoDownloader()
        video_paths, image_paths = downloader.download_all(content["visual_scenes"], workdir)
        temp_files.extend(video_paths + image_paths)
        print(f"  Downloaded {len(video_paths)} clips + {len(image_paths)} images")

        print("\n[5/7] Rendering a captioned video with voice and music...")
        output_path = os.path.join(workdir, "final_short.mp4")
        editor = SilentVideoEditor(workdir)
        editor.compose(
            image_paths=image_paths,
            script=content["voiceover_script"],
            output_path=output_path,
            target_duration=voice_duration,
            voice_path=voice_path,
            music_path=music_path,
        )
        temp_files.append(output_path)
        print(f"  Video saved: {output_path}")

        print("\n[6/7] Uploading to YouTube...")
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
            visibility=os.environ.get("YT_PRIVACY_STATUS") or "unlisted",
        )

        print("\n[7/7] Done! Voice and caption Short uploaded successfully.")

    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
    finally:
        print("\nCleaning up temporary files...")
        cleanup(temp_files)


if __name__ == "__main__":
    main()
