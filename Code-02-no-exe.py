import re
import struct
from pathlib import Path


FOLDER = Path.cwd()

# Matroska / EBML element IDs
SEGMENT = 0x18538067
INFO = 0x1549A966
TRACKS = 0x1654AE6B
TRACK_ENTRY = 0xAE
TRACK_NUMBER = 0xD7
TRACK_TYPE = 0x83
CODEC_ID = 0x86
CLUSTER = 0x1F43B675
TIMECODE = 0xE7
SIMPLE_BLOCK = 0xA3
BLOCK_GROUP = 0xA0
BLOCK = 0xA1
BLOCK_DURATION = 0x9B

TRACK_TYPE_SUBTITLE = 0x11
S_TEXT_UTF8 = "S_TEXT/UTF8"


def read_vint(data: bytes, offset: int, remove_marker: bool = False):
    """Read an EBML variable-size integer."""
    if offset >= len(data):
        raise EOFError("Unexpected end of file.")

    first = data[offset]
    mask = 0x80
    length = 1

    while length <= 8 and not (first & mask):
        mask >>= 1
        length += 1

    if length > 8 or offset + length > len(data):
        raise ValueError("Invalid EBML variable-size integer.")

    value = first
    if remove_marker:
        value &= mask - 1

    for index in range(1, length):
        value = (value << 8) | data[offset + index]

    return value, length


def read_element_id(data: bytes, offset: int):
    """Read an EBML element ID."""
    first = data[offset]
    mask = 0x80
    length = 1

    while length <= 4 and not (first & mask):
        mask >>= 1
        length += 1

    if length > 4 or offset + length > len(data):
        raise ValueError("Invalid EBML element ID.")

    value = 0
    for index in range(length):
        value = (value << 8) | data[offset + index]

    return value, length


def read_element(data: bytes, offset: int):
    """Read one EBML element header."""
    element_id, id_length = read_element_id(data, offset)
    size, size_length = read_vint(
        data,
        offset + id_length,
        remove_marker=True,
    )

    data_start = offset + id_length + size_length

    # Unknown-size elements extend to the available data boundary.
    if size == (1 << (7 * size_length)) - 1:
        return element_id, data_start, len(data), len(data)

    data_end = data_start + size
    if data_end > len(data):
        raise EOFError("EBML element extends beyond file.")

    return element_id, data_start, data_end, data_end


def read_uint(data: bytes) -> int:
    return int.from_bytes(data, byteorder="big")


def find_segment(data: bytes):
    """Find the Matroska Segment element."""
    offset = 0

    while offset < len(data):
        element_id, start, end, next_offset = read_element(data, offset)
        if element_id == SEGMENT:
            return start, end
        offset = next_offset

    raise ValueError("Matroska Segment not found.")


def parse_tracks(data: bytes, start: int, end: int):
    """Return embedded text-based SRT subtitle tracks."""
    tracks = []
    offset = start

    while offset < end:
        element_id, element_start, element_end, next_offset = read_element(
            data, offset
        )

        if element_id == TRACK_ENTRY:
            track = {}
            inner = element_start

            while inner < element_end:
                child_id, child_start, child_end, child_next = read_element(
                    data, inner
                )

                if child_id == TRACK_NUMBER:
                    track["number"] = read_uint(data[child_start:child_end])
                elif child_id == TRACK_TYPE:
                    track["type"] = read_uint(data[child_start:child_end])
                elif child_id == CODEC_ID:
                    track["codec_id"] = data[
                        child_start:child_end
                    ].decode("utf-8", errors="replace")

                inner = child_next

            if (
                track.get("type") == TRACK_TYPE_SUBTITLE
                and track.get("codec_id") == S_TEXT_UTF8
            ):
                tracks.append(track)

        offset = next_offset

    return tracks


def read_ebml_signed(data: bytes, offset: int):
    """Read an EBML signed integer."""
    raw, length = read_vint(data, offset, remove_marker=True)
    bits = 7 * length
    bias = (1 << (bits - 1)) - 1
    return raw - bias, length


def parse_xiph_lacing(payload: bytes):
    count = payload[0] + 1
    position = 1
    sizes = []

    for _ in range(count - 1):
        size = 0
        while True:
            value = payload[position]
            position += 1
            size += value
            if value != 255:
                break
        sizes.append(size)

    sizes.append(len(payload) - position - sum(sizes))

    frames = []
    for size in sizes:
        frames.append(payload[position:position + size])
        position += size

    return frames


def parse_fixed_lacing(payload: bytes):
    count = payload[0] + 1
    position = 1
    remaining = len(payload) - position

    if remaining % count:
        raise ValueError("Invalid fixed lacing.")

    size = remaining // count
    return [
        payload[position + index * size:position + (index + 1) * size]
        for index in range(count)
    ]


def parse_ebml_lacing(payload: bytes):
    count = payload[0] + 1
    position = 1

    first_size, consumed = read_vint(
        payload,
        position,
        remove_marker=True,
    )
    position += consumed

    sizes = [first_size]

    for _ in range(count - 2):
        delta, consumed = read_ebml_signed(payload, position)
        position += consumed
        sizes.append(sizes[-1] + delta)

    sizes.append(len(payload) - position - sum(sizes))

    frames = []
    for size in sizes:
        frames.append(payload[position:position + size])
        position += size

    return frames


def parse_block(block: bytes):
    """Parse a Matroska Block or SimpleBlock."""
    track_number, track_length = read_vint(
        block,
        0,
        remove_marker=True,
    )

    if len(block) < track_length + 3:
        raise ValueError("Invalid Matroska block.")

    relative_timecode = struct.unpack(
        ">h",
        block[track_length:track_length + 2],
    )[0]

    flags = block[track_length + 2]
    payload = block[track_length + 3:]
    lacing = (flags & 0x06) >> 1

    if lacing == 0:
        frames = [payload]
    elif lacing == 1:
        frames = parse_xiph_lacing(payload)
    elif lacing == 2:
        frames = parse_fixed_lacing(payload)
    elif lacing == 3:
        frames = parse_ebml_lacing(payload)
    else:
        raise ValueError("Unknown lacing mode.")

    return track_number, relative_timecode, frames


def parse_cluster(
    data: bytes,
    start: int,
    end: int,
    subtitle_track_numbers: set[int],
):
    """Extract subtitle entries from one Matroska Cluster."""
    cluster_timecode = 0
    blocks = []
    offset = start

    while offset < end:
        element_id, element_start, element_end, next_offset = read_element(
            data, offset
        )

        if element_id == TIMECODE:
            cluster_timecode = read_uint(data[element_start:element_end])

        elif element_id == SIMPLE_BLOCK:
            blocks.append(
                (
                    data[element_start:element_end],
                    None,
                )
            )

        elif element_id == BLOCK_GROUP:
            block_data = None
            duration = None
            inner = element_start

            while inner < element_end:
                child_id, child_start, child_end, child_next = read_element(
                    data, inner
                )

                if child_id == BLOCK:
                    block_data = data[child_start:child_end]
                elif child_id == BLOCK_DURATION:
                    duration = read_uint(data[child_start:child_end])

                inner = child_next

            if block_data is not None:
                blocks.append((block_data, duration))

        offset = next_offset

    subtitles = []

    for block, duration in blocks:
        try:
            track_number, relative_timecode, frames = parse_block(block)
        except (EOFError, ValueError):
            continue

        if track_number not in subtitle_track_numbers:
            continue

        timestamp = cluster_timecode + relative_timecode

        for frame in frames:
            text = frame.decode("utf-8", errors="replace").strip()
            if text:
                subtitles.append(
                    {
                        "start": timestamp,
                        "duration": duration,
                        "text": text.replace("\\N", "\n").replace("\\n", "\n"),
                    }
                )

    return subtitles


def get_timecode_scale(data: bytes, segment_start: int, segment_end: int):
    """Read Matroska TimecodeScale. Default is 1,000,000 ns."""
    offset = segment_start

    while offset < segment_end:
        element_id, start, end, next_offset = read_element(data, offset)

        if element_id == INFO:
            inner = start

            while inner < end:
                child_id, child_start, child_end, child_next = read_element(
                    data, inner
                )

                if child_id == 0x2AD7B1:
                    return read_uint(data[child_start:child_end])

                inner = child_next

        offset = next_offset

    return 1_000_000


def extract_subtitles(
    data: bytes,
    segment_start: int,
    segment_end: int,
    track_number: int,
):
    """Extract subtitle entries belonging to one track."""
    subtitles = []
    offset = segment_start

    while offset < segment_end:
        element_id, start, end, next_offset = read_element(data, offset)

        if element_id == CLUSTER:
            subtitles.extend(
                parse_cluster(
                    data,
                    start,
                    end,
                    {track_number},
                )
            )

        offset = next_offset

    return subtitles


def format_timestamp(milliseconds: float) -> str:
    milliseconds = max(0, int(round(milliseconds)))

    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    seconds, milliseconds = divmod(milliseconds, 1_000)

    return (
        f"{hours:02d}:{minutes:02d}:"
        f"{seconds:02d},{milliseconds:03d}"
    )


def write_srt(subtitles, output_file: Path, timecode_scale: int):
    """Write subtitle entries as an SRT file."""
    unit_to_ms = timecode_scale / 1_000_000

    with output_file.open("w", encoding="utf-8-sig", newline="\n") as file:
        for index, subtitle in enumerate(subtitles, start=1):
            start_ms = subtitle["start"] * unit_to_ms

            if subtitle["duration"] is not None:
                end_ms = (
                    subtitle["start"] + subtitle["duration"]
                ) * unit_to_ms
            else:
                # SimpleBlock subtitles do not carry duration.
                # Use a conservative fallback until a richer timing
                # strategy is implemented.
                end_ms = start_ms + 3_000

            file.write(f"{index}\n")
            file.write(
                f"{format_timestamp(start_ms)} --> "
                f"{format_timestamp(end_ms)}\n"
            )
            file.write(subtitle["text"])
            file.write("\n\n")


def get_episode_name(filename: str) -> str:
    """Extract SxxExx from the filename."""
    match = re.search(r"(S\d{2}E\d{2})", filename, re.IGNORECASE)
    return match.group(1).upper() if match else Path(filename).stem


def process_file(mkv_file: Path):
    """Process one MKV file."""
    print("=" * 70)
    print(f"Processing: {mkv_file.name}")

    try:
        data = mkv_file.read_bytes()
        segment_start, segment_end = find_segment(data)

        tracks_start = tracks_end = None
        offset = segment_start

        while offset < segment_end:
            element_id, start, end, next_offset = read_element(data, offset)
            if element_id == TRACKS:
                tracks_start, tracks_end = start, end
                break
            offset = next_offset

        if tracks_start is None:
            print("No Tracks element found.")
            return

        tracks = parse_tracks(data, tracks_start, tracks_end)

        if not tracks:
            print("No SRT-compatible subtitle track found.")
            print("Supported format: S_TEXT/UTF8 (SubRip/SRT).")
            return

        track = tracks[0]
        print(f"Using subtitle track {track['number']}.")

        subtitles = extract_subtitles(
            data,
            segment_start,
            segment_end,
            track["number"],
        )

        if not subtitles:
            print("No subtitle entries found.")
            return

        subtitles.sort(key=lambda item: item["start"])

        output_file = mkv_file.parent / f"{get_episode_name(mkv_file.name)}.srt"

        if output_file.exists():
            print(f"{output_file.name} already exists. Skipping.")
            return

        timecode_scale = get_timecode_scale(
            data,
            segment_start,
            segment_end,
        )

        write_srt(subtitles, output_file, timecode_scale)

        print(
            f"Saved: {output_file.name} "
            f"({len(subtitles)} subtitle entries)"
        )

    except Exception as error:
        print(f"Error: {error}")


def main():
    mkv_files = sorted(FOLDER.glob("*.mkv"))

    if not mkv_files:
        print("No MKV files found in the current directory.")
        return

    print(f"Found {len(mkv_files)} MKV file(s).\n")

    for mkv_file in mkv_files:
        process_file(mkv_file)

    print("\nFinished.")


if __name__ == "__main__":
    main()
