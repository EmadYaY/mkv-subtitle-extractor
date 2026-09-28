# MKV Subtitle Extractor

A small Windows/Python utility for extracting embedded text subtitles from MKV video files into separate `.srt` files.

## Why this exists

Some TV media players do not handle embedded **soft subtitles** in MKV files as reliably as desktop or mobile media players.

A video can contain the subtitle inside the MKV container:

```text
Movie.mkv
├── Video
├── Audio
└── Subtitle (embedded / soft subtitle)
```

A PC or phone may display that subtitle correctly, while a TV's built-in media player may fail to detect or render it.

A practical workaround is to extract the subtitle and place it beside the video:

```text
Movie.mkv
Movie.srt
```
## Parsi - پارسی:
یه ابزار ساده برای جدا کردن زیرنویس‌های داخلی فایل‌های MKV و تبدیلشون به فایل SRT جداگانه. برای وقتیه که زیرنویس روی کامپیوتر یا موبایل درست نمایش داده میشه، ولی پلیر تلویزیون با SoftSub مشکل داره. بعضا این مشکل هستش که هرچی زیرنویس استفاده میکنید مثل اون زیرنویس چسپیده نمیشه و سینک/هماهنگ نیستش، پس این ایده رو پیاده کردم که از خوده فایل امبد شده به MKV استفاده کنم و استخراجش کنم. پروژه ساده و گیکی بود امیدوارم این پروژه رو استفاده کنید و یه حرکت بیخود مثل من انجام بدید فقط برای اینکه از پایتون و AI استفاده کرده باشید :)     به قول جادی: "شاد و خندون باشیدددد"


This project automates that process for a folder of MKV files.

> **Important:** This project is not affiliated with, endorsed by, or connected to the creators, copyright holders, or distributors of any TV series or movie mentioned in examples. It operates on video files already available to the user and does not provide copyrighted video or subtitle files.

## Features

- Processes all `.mkv` files in a folder
- Detects embedded subtitle tracks
- Extracts the first available subtitle track
- Generates names such as `S02E02.srt` when `SxxExx` is present in the filename
- Keeps extracted subtitles beside the original video
- Does not modify or re-encode video files
- Provides two extraction backends:
  - **MKVToolNix backend** for broad Matroska subtitle extraction
  - **Pure Python backend** for `S_TEXT/UTF8` / SubRip-compatible subtitle tracks

## Repository structure

```text
mkv-subtitle-extractor/
├── Code.py
├── Code-02-no-exe.py
├── README.md
├── LICENSE
└── .gitignore
```

### `Code.py`

Uses MKVToolNix:

```text
mkvmerge.exe
mkvextract.exe
```

MKVToolNix must be installed separately.

The script does **not** contain a user-specific installation path. It searches the system `PATH` and common Windows installation directories. A custom directory can also be supplied with `--tool-dir`.

### `Code-02-no-exe.py`

A standalone Python implementation that parses the Matroska/EBML container directly.

It currently supports:

```text
S_TEXT/UTF8
```

which is the Matroska representation commonly used for SubRip/SRT text subtitles.

It does not require:

- MKVToolNix
- `mkvmerge.exe`
- `mkvextract.exe`
- third-party Python packages

## Requirements

### Code.py

- Windows
- Python 3.10+
- MKVToolNix

### Code-02-no-exe.py

- Python 3.10+
- No external executable
- No third-party Python package

## Usage

### Option 1: MKVToolNix backend

Install MKVToolNix from its official website:

https://mkvtoolnix.download/

Place `Code.py` in the folder containing your MKV files:

```text
Videos/
├── Code.py
├── Example.S02E01.720p.BluRay.mkv
├── Example.S02E02.720p.BluRay.mkv
└── Example.S02E03.720p.BluRay.mkv
```

Run:

```bash
python Code.py
```

The script searches for MKVToolNix automatically.

If MKVToolNix is installed somewhere else, you can specify its directory:

```bash
python Code.py --tool-dir "D:\Apps\MKVToolNix"
```

You can also process another folder:

```bash
python Code.py --folder "D:\Videos"
```

Output:

```text
Videos/
├── Example.S02E01.720p.BluRay.mkv
├── S02E01.srt
├── Example.S02E02.720p.BluRay.mkv
├── S02E02.srt
└── ...
```

### Option 2: Pure Python backend

No MKVToolNix is required.

Place `Code-02-no-exe.py` in the video folder:

```text
Videos/
├── Code-02-no-exe.py
├── Example.S02E01.720p.BluRay.mkv
├── Example.S02E02.720p.BluRay.mkv
└── ...
```

Run:

```bash
python Code-02-no-exe.py
```

The script reads the MKV/Matroska container directly and extracts the first compatible `S_TEXT/UTF8` subtitle track.

## Subtitle format support

### Currently supported

| Format | Pure Python | MKVToolNix backend |
|---|---:|---:|
| SRT / SubRip (`S_TEXT/UTF8`) | Yes | Yes |
| ASS / SSA | No | Depends on the source/target format |
| PGS | No | Extractable, but not an SRT text conversion |
| VobSub | No | Extractable, but not an SRT text conversion |

The project currently focuses on **text-based SRT subtitles**.

Image-based subtitle formats such as PGS are fundamentally different: they contain rendered subtitle images rather than subtitle text. Converting those to SRT requires OCR and is outside the current scope.

## Important limitation of the Pure Python backend

Matroska `SimpleBlock` subtitle entries do not always contain an explicit subtitle duration. In those cases, the current Pure Python implementation uses a fallback duration when generating the SRT timing.

For maximum compatibility and more complete Matroska handling, the MKVToolNix backend is recommended when available.

The Pure Python implementation is intentionally kept dependency-free and focused on the SRT use case.

## Copyright and legal notice

This project is a general-purpose subtitle extraction utility.

It does not include, distribute, host, or link to copyrighted movies, TV episodes, or subtitle files.

Users are responsible for ensuring that their use of video and subtitle material complies with the applicable copyright laws, licenses, and terms of service in their jurisdiction.

Examples using the names of copyrighted works are provided solely to illustrate file naming and software usage.

## License

This project is released under the MIT License. See [LICENSE](LICENSE).
