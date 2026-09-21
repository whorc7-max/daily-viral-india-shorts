import os
import sys
import shutil
import tempfile
import traceback

from src.script_generator import ScriptGenerator
from src.downloader import VideoDownloader
from src.silent_editor import SilentVideoEditor
from src.uploader import YouTubeUploader


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

        print("\n[1/5] Finding a current India trend and writing one Hindi Short...")
        content = ScriptGenerator().generate()
        print(f"  Title: {content['title']}")
        print(f"  Keywords: {', '.join(content['visual_keywords'])}")

        print("\n[2/5] Downloading optional licensed stock images...")
        downloader = VideoDownloader()
        video_paths, image_paths = downloader.download_all(content["visual_keywords"], workdir)
        temp_files.extend(video_paths + image_paths)
        print(f"  Downloaded {len(video_paths)} clips + {len(image_paths)} images")

        print("\n[3/5] Rendering a silent caption video...")
        output_path = os.path.join(workdir, "final_short.mp4")
        editor = SilentVideoEditor(workdir)
        editor.compose(
            image_paths=image_paths,
            script=content["voiceover_script"],
            output_path=output_path,
            target_duration=float(content.get("duration_seconds", 55)),
        )
        temp_files.append(output_path)
        print(f"  Video saved: {output_path}")

        print("\n[4/5] Uploading to YouTube...")
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

        print("\n[5/5] Done! Silent caption Short uploaded successfully.")

    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
    finally:
        print("\nCleaning up temporary files...")
        cleanup(temp_files)


if __name__ == "__main__":
    main()
