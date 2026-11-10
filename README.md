# image-format-checker-cli

Check images are the format you allow, fail CI on a wrong format.

[![CI](https://github.com/haiderstudio/image-format-checker-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/haiderstudio/image-format-checker-cli/actions/workflows/ci.yml) [![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

## What it does

`image_format_checker` reads each image's real format
straight from its magic bytes and checks it against the
formats you allow:

- A BMP or TIFF slipped into a web folder will not display
  right and bloats every page that loads it, and the person
  who uploaded it never notices — the file itself looks
  fine on disk. Bloggers and site owners upload them
  constantly. This tool reports every file in a disallowed
  format, with its file and its real format, and exits 1
  when any problem is found — so it can fail a CI run. A
  clean folder exits 0.
- The format comes from the magic bytes, never from the
  extension — a PNG renamed to `.jpg` is still reported
  as a PNG. That is the whole point: extensions lie, bytes
  do not.
- The default allow list is PNG, JPEG, and WebP — the
  formats every browser shows well. `--allow` sets your
  own list, for example `--allow png,jpg,webp,gif`. Names
  are case-insensitive, and `jpeg` means `jpg`.
- Formats are read from the headers only, so the tool
  never decodes a pixel: a PNG's signature, a JPEG's SOI
  marker, a GIF's header, a BMP's signature, a WebP's
  RIFF chunk, a TIFF's byte-order mark, an ICO header,
  and an AVIF or HEIC file's ftyp brand.
- A file whose format cannot be read — an empty file, a
  truncated header, or a file that is not an image at all
  — is reported as a problem, not skipped, because a file
  that cannot be checked cannot be trusted.
- Images come from the command line (one or more), or
  from a folder walk: every `.png`, `.jpg`, `.jpeg`,
  `.gif`, `.bmp`, `.webp`, `.tif`, `.tiff`, `.ico`,
  `.avif`, and `.heic` file under a folder, recursively by
  default (`--no-recursive` stops at the top level).
  `.git` folders are never walked, and directory links are
  never followed, so a link cycle cannot loop the check.
- `--exclude PATTERN` skips files by glob, for example
  `--exclude 'draft-*'`. It can be repeated. A file passed
  directly on the command line is always checked, even if
  it matches an exclude pattern and even if it has no
  image extension.
- `--stdin` reads one image from standard input.
- `--json` prints the result as machine-readable JSON (the
  summary goes to standard error, so standard output stays
  clean JSON).
- It is report-only and runs fully offline: it never
  converts an image, sends nothing anywhere, and needs no
  API key. No Pillow, no image library of any kind —
  formats are read from the headers by hand.

## What it does NOT do

- It does not convert, resize, or rewrite an image. A
  disallowed image is reported; converting it is your job.
- It does not check pixel dimensions — that is repo #51's
  `image-dimension-checker-cli`. This tool's one job is
  format.
- It does not check alt text — that is repo #30's
  `image-alt-checker-cli`.
- It does not fetch images from a live site. Every input
  is a local file or standard input — an image that only
  exists on the web is not this tool's job.

## Who it is for

Anyone who puts images on a site and wants only web-safe
formats to ship: a blogger checking a batch of uploads, a
developer adding a CI step that fails the build when a BMP
or TIFF sneaks in, or anyone tidying a folder of old
photos. A wrong format is invisible in the file itself —
this catches it before it goes live.

## How this differs from similar tools

The exact name `image-format-checker-cli` matches 0
repositories on GitHub (checked Nov 8, 2026), and the
wider field is small: `image format checker` matches 39
repositories. The top ones are noise — a Docker image
verifying C++ code format, a YOLO bounding-box tool, a
shell formatter. The closest real rivals are
mikyll/ImageFormatChecker, 2 stars, a bash script that
checks image DIMENSIONS recursively (a different job),
and capt-jack00/ImageFormatChecker, 0 stars, a small C++
program that detects one file's format, with no tests, no
allow list, no folder walk, and no CI gate. None of them
is a tested CLI that walks a folder of local image files,
reads the real format from the magic bytes with no image
library, checks it against an allow list you set, and
exits 1 for CI. This tool does that one job: a Python
standard-library-only CLI that checks PNG, JPEG, GIF,
BMP, WebP, TIFF, ICO, AVIF, and HEIC files against the
formats you allow — no install beyond Python, no website,
no network.

## Install

Python standard library only — no packages to download. You need
Python 3.8 or newer. Clone the repo and run it in place:

```
git clone https://github.com/haiderstudio/image-format-checker-cli.git
cd image-format-checker-cli
python3 src/image_format_checker.py examples/good.png
```

```
examples/good.png: PNG
OK — 1 file(s) checked, all images are in an allowed format.
```

## Usage

Check one image against the default allow list (PNG, JPEG, WebP):

```
python3 src/image_format_checker.py examples/good.png
```

```
examples/good.png: PNG
OK — 1 file(s) checked, all images are in an allowed format.
```

Check an image in a disallowed format:

```
python3 src/image_format_checker.py examples/photo.bmp
```

```
FAIL examples/photo.bmp: BMP — not an allowed format (BMP; allowed: jpg, png, webp)
Checked 1 file(s), 1 problem(s) in 1 file(s).
```

Allow GIF too, for this run:

```
python3 src/image_format_checker.py --allow png,jpg,webp,gif examples/photo.gif
```

```
examples/photo.gif: GIF
OK — 1 file(s) checked, all images are in an allowed format.
```

A PNG renamed to `.jpg` is still detected as a PNG — by its bytes, not its name:

```
python3 src/image_format_checker.py examples/misnamed.jpg
```

```
examples/misnamed.jpg: PNG
OK — 1 file(s) checked, all images are in an allowed format.
```

Check an empty file — reported, not skipped:

```
python3 src/image_format_checker.py examples/empty.png
```

```
FAIL examples/empty.png — cannot read format (empty file)
Checked 1 file(s), 1 problem(s) in 1 file(s).
```

Check a whole folder:

```
python3 src/image_format_checker.py examples/
```

```
FAIL examples/empty.png — cannot read format (empty file)
examples/good.jpg: JPEG
examples/good.png: PNG
examples/good.webp: WebP
examples/misnamed.jpg: PNG
FAIL examples/photo.bmp: BMP — not an allowed format (BMP; allowed: jpg, png, webp)
FAIL examples/photo.gif: GIF — not an allowed format (GIF; allowed: jpg, png, webp)
FAIL examples/photos/banner.gif: GIF — not an allowed format (GIF; allowed: jpg, png, webp)
examples/photos/hero.png: PNG
Checked 9 file(s), 4 problem(s) in 4 file(s).
```

Check one image from standard input:

```
python3 src/image_format_checker.py --stdin < examples/good.png
```

```
<stdin>: PNG
OK — 1 file(s) checked, all images are in an allowed format.
```

Machine-readable output with `--json` (the summary goes to
standard error, so standard output stays clean JSON):

```
python3 src/image_format_checker.py --json examples/photo.bmp
```

```
{
  "files": [
    {
      "file": "examples/photo.bmp",
      "format": "BMP",
      "problems": [
        {
          "line": 0,
          "reason": "not an allowed format (BMP; allowed: jpg, png, webp)"
        }
      ]
    }
  ],
  "summary": {
    "checked": 1,
    "files_with_problems": 1,
    "problems": 1,
    "skipped": 0,
    "allowed": [
      "jpg",
      "png",
      "webp"
    ]
  }
}
```

Exit codes: 0 when every checked image is in an allowed
format, 1 when any image is in a disallowed format or
unreadable, 2 for a usage problem (no image files given, a
bad flag, a bad `--allow` value, or a missing file or
folder).

## Examples

### 1. A folder of uploads, default allow list

`examples/` holds nine images. Five pass, four fail — an
empty file, two GIFs, and a BMP:

```
python3 src/image_format_checker.py examples/
```

```
FAIL examples/empty.png — cannot read format (empty file)
examples/good.jpg: JPEG
examples/good.png: PNG
examples/good.webp: WebP
examples/misnamed.jpg: PNG
FAIL examples/photo.bmp: BMP — not an allowed format (BMP; allowed: jpg, png, webp)
FAIL examples/photo.gif: GIF — not an allowed format (GIF; allowed: jpg, png, webp)
FAIL examples/photos/banner.gif: GIF — not an allowed format (GIF; allowed: jpg, png, webp)
examples/photos/hero.png: PNG
Checked 9 file(s), 4 problem(s) in 4 file(s).
```

### 2. The same folder, GIF allowed as well

```
python3 src/image_format_checker.py --allow png,jpg,webp,gif examples/
```

```
FAIL examples/empty.png — cannot read format (empty file)
examples/good.jpg: JPEG
examples/good.png: PNG
examples/good.webp: WebP
examples/misnamed.jpg: PNG
FAIL examples/photo.bmp: BMP — not an allowed format (BMP; allowed: gif, jpg, png, webp)
examples/photo.gif: GIF
examples/photos/banner.gif: GIF
examples/photos/hero.png: PNG
Checked 9 file(s), 2 problem(s) in 2 file(s).
```

### 3. The bundled examples, all at once

```
sh examples/run-example.sh
```

The script checks one good image (pass), then the GIF
against the default list (fail, on purpose), then the
misnamed file (pass — its bytes say PNG), then the whole
`examples/` folder (fail, on purpose — it picks up the
empty file, the BMP, and both GIFs). Its full output is in
`examples/sample-output.md`, ending with `Checked 9
file(s), 4 problem(s) in 4 file(s).` The failing runs exit
1, which is the expected result — the script ends with
exit 0 so it can be run as a demo.

## How it is tested

Tests, standard library `unittest` only, no packages to install:

```
python3 tests/test_image_format_checker.py
```

The tests cover: format detection (PNG, JPEG, GIF 87a and
89a, BMP, WebP, TIFF little- and big-endian, ICO, AVIF
and HEIC ftyp brands including mif1 with and without an
avif compatible brand, unknown ftyp brands, RIFF without
WEBP, truncated headers, text that is not an image, empty
input, and random bytes), the allow list (defaults,
comma lists, repeated flags, `jpeg` meaning `jpg`,
`tif` meaning `tiff`, case-insensitive names, unknown
formats), file collection (good file, disallowed file, a
PNG renamed to `.jpg`, empty file, text file, missing
file, input files left unchanged), folder walking (only
image extensions, `.git` skipped, `--no-recursive`,
`--exclude`, a direct file checked even without an image
extension and even if excluded, uppercase extensions,
missing path), the CLI (exit 0/1/2, each flag, `--stdin`
good and bad and empty, `--json` output, `--version`, bad
flags, missing paths, empty folders, a folder summary
count, and every bundled example file read back with its
real format), the bundled examples (sample output compared
byte-for-byte against a fresh run, and the README-quoted
outputs checked against it), and hygiene checks (no
placeholder text, no absolute paths, stdlib imports only,
`.env` first in `.gitignore`, CI file runs the test file).

## Contributing

Small, focused improvements are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT — see [LICENSE](LICENSE).

## Original work

This tool was written from scratch for this repo. The idea
of checking image formats is not new — the similar tools
named above (the 2-star bash dimension script, the 0-star
C++ format detector) are listed in "How this differs" —
but every line of code here is original, and the tool
builds on nothing but Python's standard library.
