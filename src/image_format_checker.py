#!/usr/bin/env python3
"""Check image files are in an allowed format, fail CI on a wrong format.

Run: python3 src/image_format_checker.py examples/good.png
     python3 src/image_format_checker.py examples/
     python3 src/image_format_checker.py --allow png,jpg,webp examples/

The problem is quiet: a BMP or TIFF slipped into a web
folder will not display right and bloats every page that
loads it, and the person who uploaded it never notices —
the file itself looks fine on disk. Bloggers and site
owners upload them constantly. This tool reads each
image's real format from its magic bytes — not from its
extension, so a PNG renamed to .jpg is still caught as a
PNG — checks it against the formats you allow (PNG, JPEG,
and WebP by default), reports every file in a disallowed
format with its file and its real format, and exits 1 when
any problem is found, so it can fail a CI run. A clean
folder exits 0.

Formats are read from the file headers only, so the tool
never decodes a pixel: a PNG's signature, a JPEG's SOI
marker, a GIF's header, a BMP's signature, a WebP's RIFF
chunk, a TIFF's byte-order mark, an ICO header, and an
AVIF or HEIC file's ftyp brand. A file whose format cannot
be read — an empty file, a truncated header, or a file
that is not an image at all — is reported as a problem,
not skipped, because a file that cannot be checked cannot
be trusted.

It never rewrites a file. It is report-only and runs fully
offline: it sends nothing anywhere and needs no API key.

Exit codes: 0 when every checked image is in an allowed
format, 1 when any image is in a disallowed format or
unreadable, 2 for a usage or input problem (a missing
path, a bad flag, a bad --allow value, or no image files
to check).

Python standard library only. No Pillow, no image library
of any kind — formats are read from the headers by hand.
"""

import argparse
import fnmatch
import json
import os
import sys
from pathlib import Path

VERSION = "1.0.0"

IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".webp",
    ".tif",
    ".tiff",
    ".ico",
    ".avif",
    ".heic",
}
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
DEFAULT_ALLOWED = ("png", "jpg", "webp")
SUPPORTED_FORMATS = "PNG, JPEG, GIF, BMP, WebP, TIFF, ICO, AVIF, HEIC"

# Canonical short names, in the order they are shown to the user.
KNOWN_FORMATS = ("png", "jpg", "gif", "bmp", "webp", "tiff", "ico", "avif", "heic")

# Spellings a user may type that mean a canonical name.
_FORMAT_ALIASES = {
    "jpeg": "jpg",
    "tif": "tiff",
    "jfif": "jpg",
}


def _canonical(name):
    """Return the canonical short name for a format, or None.

    Matching is case-insensitive, and "jpeg" means "jpg".
    """
    cleaned = name.strip().lower()
    if cleaned in KNOWN_FORMATS:
        return cleaned
    return _FORMAT_ALIASES.get(cleaned)


def _ftyp_format(data):
    """Return AVIF or HEIC from an ftyp box, or None.

    The box starts with a 4-byte size, then "ftyp", then the
    major brand. avif/avis means AVIF; heic/heix/hevc/hevx
    means HEIC. mif1/msf1 are generic HEIF brands, so the
    compatible-brand list after them is checked for "avif"
    first — a file that lists avif there is an AVIF file,
    otherwise it is HEIC.
    """
    if len(data) < 12 or data[4:8] != b"ftyp":
        return None
    major = data[8:12].decode("ascii", "ignore").strip().lower()
    if major in ("avif", "avis"):
        return "AVIF"
    if major in ("heic", "heix", "hevc", "hevx"):
        return "HEIC"
    if major in ("mif1", "msf1"):
        rest = data[16:]
        for pos in range(0, len(rest) - 3, 4):
            if rest[pos:pos + 4] == b"avif":
                return "AVIF"
        return "HEIC"
    return None


def detect_format(data):
    """Return the image format name for raw file bytes.

    The format comes from the magic bytes, never from the
    file name. Raises ValueError with a plain reason when
    the format cannot be read: empty input, a truncated
    header, or a file that is not a supported image at all.
    """
    if not data:
        raise ValueError("cannot read format (empty file)")
    if data[:8] == PNG_SIGNATURE:
        return "PNG"
    if data[:3] == b"\xff\xd8\xff":
        return "JPEG"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "GIF"
    if data[:2] == b"BM":
        return "BMP"
    if data[:4] == b"RIFF" and len(data) >= 12 and data[8:12] == b"WEBP":
        return "WebP"
    if data[:4] in (b"II*\x00", b"MM\x00*"):
        return "TIFF"
    if data[:4] == b"\x00\x00\x01\x00":
        return "ICO"
    ftyp = _ftyp_format(data)
    if ftyp is not None:
        return ftyp
    raise ValueError(f"not a supported image file ({SUPPORTED_FORMATS})")


def check_format(image_format, allowed):
    """Return the problems for one image against the allowed list.

    allowed is a set of canonical short names. A format on
    the list passes; anything else is one problem.
    """
    short = _canonical(image_format)
    if short in allowed:
        return []
    return [
        {
            "line": 0,
            "reason": (
                f"not an allowed format ({image_format}; "
                f"allowed: {', '.join(sorted(allowed))})"
            ),
        }
    ]


def collect_from_file(path, allowed):
    """Return (problems, skipped, info) for one file.

    problems is a list of dicts; skipped is always False —
    nothing is skipped, a file that cannot be read is a
    problem. info is the detected format name, or None when
    the format could not be read.
    """
    try:
        data = path.read_bytes()
    except OSError as exc:
        return (
            [
                {
                    "line": 0,
                    "reason": f"cannot read file: {exc.strerror}",
                }
            ],
            False,
            None,
        )
    try:
        image_format = detect_format(data)
    except ValueError as exc:
        return ([{"line": 0, "reason": str(exc)}], False, None)
    return (check_format(image_format, allowed), False, image_format)


def _is_image(name):
    return Path(name).suffix.lower() in IMAGE_EXTENSIONS


def gather(paths, exclude, recursive, allowed):
    """Walk the given paths and return (entries, checked, skipped).

    entries is a list of (file, problem); checked is a list of
    one dict per file the tool tried, with file and format
    (None when the format could not be read); skipped is
    always an empty list — every file with an image
    extension is either checked or reported, never skipped.
    A file passed on the command line is always checked, even
    if it matches --exclude and even if it has no image
    extension. Inside a folder, only image files are checked.
    """
    entries = []
    checked = []
    skipped = []
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            raise FileNotFoundError(raw)
        if path.is_file():
            problems, _was_skipped, info = collect_from_file(path, allowed)
            checked.append({"file": str(path), "format": info})
            for problem in problems:
                entries.append((str(path), problem))
            continue
        if recursive:
            for dirpath, dirnames, filenames in _walk(path):
                for name in filenames:
                    if not _is_image(name):
                        continue
                    candidate = Path(dirpath) / name
                    if _excluded(candidate, path, exclude):
                        continue
                    problems, _was_skipped, info = collect_from_file(
                        candidate, allowed
                    )
                    checked.append({"file": str(candidate), "format": info})
                    for problem in problems:
                        entries.append((str(candidate), problem))
        else:
            for candidate in sorted(path.iterdir()):
                if not candidate.is_file():
                    continue
                if not _is_image(candidate.name):
                    continue
                if _excluded(candidate, path, exclude):
                    continue
                problems, _was_skipped, info = collect_from_file(
                    candidate, allowed
                )
                checked.append({"file": str(candidate), "format": info})
                for problem in problems:
                    entries.append((str(candidate), problem))
    return entries, checked, skipped


def _walk(root):
    """os.walk that never enters .git and never follows links."""
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d != ".git")
        yield dirpath, dirnames, sorted(filenames)


def _excluded(candidate, root, patterns):
    name = candidate.name
    try:
        rel = str(candidate.relative_to(root))
    except ValueError:
        rel = name
    return any(
        fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(rel, pattern)
        for pattern in patterns
    )


def _format_problem(location, problem, checked):
    detected = ""
    for entry in checked:
        if entry["file"] == location and entry["format"] is not None:
            detected = f": {entry['format']}"
            break
    return f"FAIL {location}{detected} — {problem['reason']}"


def _summary_line(checked, problems):
    total = len(problems)
    bad_files = len({f for f, _p in problems})
    if total:
        return (
            f"Checked {len(checked)} file(s), {total} "
            f"problem(s) in {bad_files} file(s)."
        )
    return (
        f"OK — {len(checked)} file(s) checked, "
        f"all images are in an allowed format."
    )


def parse_allow(values):
    """Return a set of canonical short names from --allow values.

    Each value may hold one format or several separated by
    commas. Raises ValueError naming the first unknown one.
    """
    allowed = set()
    for value in values:
        for part in value.split(","):
            name = _canonical(part)
            if name is None:
                raise ValueError(part.strip())
            allowed.add(name)
    return allowed


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="image-format-checker-cli",
        description="Check images are in an allowed format.",
    )
    parser.add_argument("paths", nargs="*", help="files or folders to check")
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="read one image from standard input",
    )
    parser.add_argument(
        "--allow",
        action="append",
        default=[],
        metavar="FMT,...",
        help=(
            "formats to allow, comma-separated "
            "(default: png,jpg,webp; repeatable)"
        ),
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="PATTERN",
        help="skip files matching this glob (repeatable)",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="do not walk into subfolders",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the result as JSON (summary goes to stderr)",
    )
    parser.add_argument("--version", action="store_true", help="print the version")
    args = parser.parse_args(argv)

    if args.version:
        print(f"image-format-checker-cli {VERSION}")
        return 0

    try:
        allowed = parse_allow(args.allow) if args.allow else set(DEFAULT_ALLOWED)
    except ValueError as exc:
        print(
            "error: unknown format in --allow: "
            f"{exc} (known: {', '.join(KNOWN_FORMATS)})",
            file=sys.stderr,
        )
        return 2

    entries = []
    checked = []
    skipped = []
    try:
        if args.paths:
            found, found_checked, found_skipped = gather(
                args.paths,
                args.exclude,
                not args.no_recursive,
                allowed,
            )
            entries.extend(found)
            checked.extend(found_checked)
            skipped.extend(found_skipped)
    except FileNotFoundError as exc:
        print(f"error: no such file or folder: {exc}", file=sys.stderr)
        return 2

    if args.stdin:
        data = sys.stdin.buffer.read()
        try:
            image_format = detect_format(data)
        except ValueError as exc:
            entries.append(
                ("<stdin>", {"line": 0, "reason": str(exc)})
            )
            checked.append({"file": "<stdin>", "format": None})
        else:
            checked.append({"file": "<stdin>", "format": image_format})
            for problem in check_format(image_format, allowed):
                entries.append(("<stdin>", problem))

    if not checked:
        print("error: no image files to check", file=sys.stderr)
        return 2

    problems = entries
    bad_files = len({f for f, _p in problems})
    total = len(problems)
    summary = _summary_line(checked, problems)

    if args.json:
        files = []
        for entry in checked:
            file_problems = [p for f, p in problems if f == entry["file"]]
            files.append(
                {
                    "file": entry["file"],
                    "format": entry["format"],
                    "problems": file_problems,
                }
            )
        result = {
            "files": files,
            "summary": {
                "checked": len(checked),
                "files_with_problems": bad_files,
                "problems": total,
                "skipped": len(skipped),
                "allowed": sorted(allowed),
            },
        }
        print(json.dumps(result, indent=2))
        print(summary, file=sys.stderr)
        return 1 if problems else 0

    for entry in checked:
        file_problems = [p for f, p in problems if f == entry["file"]]
        if file_problems:
            for problem in file_problems:
                print(_format_problem(entry["file"], problem, checked))
        else:
            print(f"{entry['file']}: {entry['format']}")
    print(summary)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
