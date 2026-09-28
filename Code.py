import argparse
import re
import shutil
import subprocess
from pathlib import Path


DEFAULT_WINDOWS_PATHS = [
    Path(r"C:\Program Files\MKVToolNix"),
    Path(r"C:\Program Files (x86)\MKVToolNix"),
]


def find_tool(name: str, tool_dir: Path | None = None) -> Path | None:
    """Find an MKVToolNix executable without hard-coding a user-specific path."""
    if tool_dir:
        candidate = tool_dir / name
        if candidate.exists():
            return candidate

    from_path = shutil.which(name)
    if from_path:
        return Path(from_path)

    for directory in DEFAULT_WINDOWS_PATHS:
        candidate = directory / name
        if candidate.exists():
            return candidate

    return None


def get_subtitle_tracks(mkvmerge: Path, mkv_file: Path) -> list[int]:
    """Return subtitle track IDs reported by mkvmerge."""
    result = subprocess.run(
        [str(mkvmerge), "-i", str(mkv_file)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    output = result.stdout + result.stderr

    return [
        int(track_id)
        for track_id in re.findall(
            r"Track ID (\d+): subtitles",
            output,
            re.IGNORECASE,
        )
    ]


def get_episode_name(filename: str) -> str:
    """Extract SxxExx from a filename, or fall back to the filename stem."""
    match = re.search(r"(S\d{2}E\d{2})", filename, re.IGNORECASE)
    return match.group(1).upper() if match else Path(filename).stem


def process_file(
    mkvmerge: Path,
    mkvextract: Path,
    mkv_file: Path,
) -> None:
    """Extract the first subtitle track from one MKV file."""
    print("=" * 70)
    print(f"Processing: {mkv_file.name}")

    tracks = get_subtitle_tracks(mkvmerge, mkv_file)

    if not tracks:
        print("No subtitle track found.")
        return

    track_id = tracks[0]
    episode = get_episode_name(mkv_file.name)
    output_file = mkv_file.parent / f"{episode}.srt"

    if output_file.exists():
        print(f"{output_file.name} already exists. Skipping.")
        return

    result = subprocess.run(
        [
            str(mkvextract),
            "tracks",
            str(mkv_file),
            f"{track_id}:{output_file}",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if result.returncode == 0 and output_file.exists():
        print(f"Saved: {output_file.name}")
    else:
        print("Extraction failed.")
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract the first embedded subtitle track from MKV files."
    )
    parser.add_argument(
        "--tool-dir",
        type=Path,
        help="Directory containing mkvmerge.exe and mkvextract.exe.",
    )
    parser.add_argument(
        "--folder",
        type=Path,
        default=Path.cwd(),
        help="Folder containing MKV files. Defaults to the current directory.",
    )
    args = parser.parse_args()

    folder = args.folder.resolve()
    mkvmerge = find_tool("mkvmerge.exe", args.tool_dir)
    mkvextract = find_tool("mkvextract.exe", args.tool_dir)

    if not mkvmerge or not mkvextract:
        print("MKVToolNix was not found.")
        print("Install MKVToolNix or provide its directory with --tool-dir.")
        return

    mkv_files = sorted(folder.glob("*.mkv"))

    if not mkv_files:
        print(f"No MKV files found in: {folder}")
        return

    print(f"Found {len(mkv_files)} MKV file(s).")
    print(f"Using mkvmerge: {mkvmerge}")
    print(f"Using mkvextract: {mkvextract}\n")

    for mkv_file in mkv_files:
        process_file(mkvmerge, mkvextract, mkv_file)

    print("\nFinished.")


if __name__ == "__main__":
    main()
