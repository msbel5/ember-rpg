"""Stitch PNG frames from automation recording into MP4 video.

Usage:
    python stitch_video.py <frames_dir> [output.mp4] [--fps 2]

Requires ffmpeg in PATH.
Frames must be named frame_0000.png, frame_0001.png, etc.
"""
import argparse
import subprocess
import sys
from pathlib import Path


def stitch(frames_dir: Path, output: Path, fps: int = 2) -> bool:
    pattern = frames_dir / "frame_%04d.png"
    if not any(frames_dir.glob("frame_*.png")):
        print(f"No frame_*.png files found in {frames_dir}")
        return False

    frame_count = len(list(frames_dir.glob("frame_*.png")))
    print(f"Stitching {frame_count} frames at {fps} fps -> {output}")

    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", str(pattern),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
        str(output),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ffmpeg failed: {result.stderr}")
        return False

    print(f"Video saved: {output} ({frame_count} frames, {frame_count / fps:.1f}s)")
    return True


def main():
    parser = argparse.ArgumentParser(description="Stitch PNG frames into MP4")
    parser.add_argument("frames_dir", type=Path, help="Directory containing frame_NNNN.png files")
    parser.add_argument("output", type=Path, nargs="?", default=None, help="Output video path (default: frames_dir/recording.mp4)")
    parser.add_argument("--fps", type=int, default=2, help="Frames per second (default: 2)")
    args = parser.parse_args()

    if args.output is None:
        args.output = args.frames_dir / "recording.mp4"

    if not args.frames_dir.is_dir():
        print(f"Directory not found: {args.frames_dir}")
        sys.exit(1)

    success = stitch(args.frames_dir, args.output, args.fps)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
