#!/usr/bin/env python3
"""Tests for image-format-checker-cli. Standard library unittest only.

Run from the repo root: python3 tests/test_image_format_checker.py
"""

import io
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

import image_format_checker as ifc  # noqa: E402

ALLOWED_STDLIB = {
    "argparse",
    "fnmatch",
    "json",
    "os",
    "sys",
    "pathlib",
}


def run_cli(argv, stdin_bytes=None):
    """Run main() in-process and capture (exit code, stdout, stderr)."""
    out = io.StringIO()
    err = io.StringIO()
    old_stdin = sys.stdin
    if stdin_bytes is not None:
        sys.stdin = _FakeStdin(stdin_bytes)
    try:
        with redirect_stdout(out), redirect_stderr(err):
            code = ifc.main(argv)
    finally:
        sys.stdin = old_stdin
    return code, out.getvalue(), err.getvalue()


class _FakeStdin:
    """Minimal stdin with a .buffer, for --stdin tests."""

    def __init__(self, data):
        self.buffer = io.BytesIO(data)


def png_bytes():
    """A minimal PNG: signature + IHDR + IEND."""
    return (
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", 13)
        + b"IHDR"
        + struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
        + b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def jpeg_bytes():
    """A minimal JPEG: SOI + APP0 JFIF + EOI."""
    return (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        + b"\xff\xd9"
    )


def gif_bytes(variant="89a"):
    """A minimal GIF header, 87a or 89a."""
    return b"GIF" + variant.encode("ascii") + struct.pack("<HH", 1, 1) + b"\x80\x00\x00"


def bmp_bytes():
    """A minimal BMP: file header + 40-byte DIB header."""
    return (
        b"BM"
        + struct.pack("<IHHI", 54, 0, 0, 54)
        + struct.pack("<IiiHHIIiiII", 40, 1, 1, 1, 24, 0, 0, 0, 0, 0, 0)
    )


def webp_bytes():
    """A minimal WebP: RIFF + WEBP + VP8L chunk."""
    return (
        b"RIFF"
        + struct.pack("<I", 20)
        + b"WEBP"
        + b"VP8L"
        + struct.pack("<I", 8)
        + b"\x2f\x00\x00\x00\x00\x00\x00\x00"
    )


def tiff_bytes(big_endian=False):
    """A minimal TIFF header, little-endian or big-endian."""
    if big_endian:
        return b"MM\x00*" + struct.pack(">I", 8)
    return b"II*\x00" + struct.pack("<I", 8)


def ico_bytes():
    """A minimal ICO: header + one directory entry."""
    return (
        b"\x00\x00\x01\x00"
        + struct.pack("<H", 1)
        + struct.pack("<BBBBHHII", 16, 16, 0, 0, 1, 32, 48, 22)
    )


def ftyp_bytes(major=b"avif", compat=()):
    """An ftyp box with the given major brand and compatible brands."""
    body = b"ftyp" + major + struct.pack(">I", 0) + b"".join(compat)
    return struct.pack(">I", len(body) + 4) + body


class DetectFormatTests(unittest.TestCase):
    def test_png_signature(self):
        self.assertEqual(ifc.detect_format(png_bytes()), "PNG")

    def test_png_signature_only_is_enough(self):
        self.assertEqual(ifc.detect_format(b"\x89PNG\r\n\x1a\n"), "PNG")

    def test_jpeg_soi(self):
        self.assertEqual(ifc.detect_format(jpeg_bytes()), "JPEG")

    def test_jpeg_soi_only_is_enough(self):
        self.assertEqual(ifc.detect_format(b"\xff\xd8\xff"), "JPEG")

    def test_gif89a(self):
        self.assertEqual(ifc.detect_format(gif_bytes("89a")), "GIF")

    def test_gif87a(self):
        self.assertEqual(ifc.detect_format(gif_bytes("87a")), "GIF")

    def test_bmp(self):
        self.assertEqual(ifc.detect_format(bmp_bytes()), "BMP")

    def test_bmp_signature_only_is_enough(self):
        self.assertEqual(ifc.detect_format(b"BM"), "BMP")

    def test_webp(self):
        self.assertEqual(ifc.detect_format(webp_bytes()), "WebP")

    def test_tiff_little_endian(self):
        self.assertEqual(ifc.detect_format(tiff_bytes()), "TIFF")

    def test_tiff_big_endian(self):
        self.assertEqual(ifc.detect_format(tiff_bytes(big_endian=True)), "TIFF")

    def test_ico(self):
        self.assertEqual(ifc.detect_format(ico_bytes()), "ICO")

    def test_avif_major_brand(self):
        self.assertEqual(ifc.detect_format(ftyp_bytes(b"avif")), "AVIF")

    def test_avis_major_brand_is_avif(self):
        self.assertEqual(ifc.detect_format(ftyp_bytes(b"avis")), "AVIF")

    def test_heic_major_brand(self):
        self.assertEqual(ifc.detect_format(ftyp_bytes(b"heic")), "HEIC")

    def test_heix_major_brand_is_heic(self):
        self.assertEqual(ifc.detect_format(ftyp_bytes(b"heix")), "HEIC")

    def test_mif1_with_avif_compat_is_avif(self):
        data = ftyp_bytes(b"mif1", (b"avif", b"mif1"))
        self.assertEqual(ifc.detect_format(data), "AVIF")

    def test_mif1_without_avif_compat_is_heic(self):
        data = ftyp_bytes(b"mif1", (b"mif1",))
        self.assertEqual(ifc.detect_format(data), "HEIC")

    def test_unknown_ftyp_brand_is_not_an_image(self):
        with self.assertRaises(ValueError) as ctx:
            ifc.detect_format(ftyp_bytes(b"mp42"))
        self.assertIn("not a supported image file", str(ctx.exception))

    def test_riff_without_webp_is_not_an_image(self):
        with self.assertRaises(ValueError) as ctx:
            ifc.detect_format(b"RIFF\x10\x00\x00\x00WAVE")
        self.assertIn("not a supported image file", str(ctx.exception))

    def test_truncated_ftyp_is_not_an_image(self):
        with self.assertRaises(ValueError):
            ifc.detect_format(b"\x00\x00\x00\x10ftyp")

    def test_text_is_not_an_image(self):
        with self.assertRaises(ValueError) as ctx:
            ifc.detect_format(b"this is not an image\n")
        self.assertIn("not a supported image file", str(ctx.exception))

    def test_empty_bytes_cannot_be_read(self):
        with self.assertRaises(ValueError) as ctx:
            ifc.detect_format(b"")
        self.assertIn("empty file", str(ctx.exception))

    def test_random_bytes_are_not_an_image(self):
        with self.assertRaises(ValueError):
            ifc.detect_format(b"\x01\x02\x03\x04\x05\x06\x07\x08")


class AllowParsingTests(unittest.TestCase):
    def test_default_allowed(self):
        self.assertEqual(set(ifc.DEFAULT_ALLOWED), {"png", "jpg", "webp"})

    def test_single_value(self):
        self.assertEqual(ifc.parse_allow(["png"]), {"png"})

    def test_comma_list(self):
        self.assertEqual(
            ifc.parse_allow(["png,jpg,gif"]), {"png", "jpg", "gif"}
        )

    def test_repeatable_values_merge(self):
        self.assertEqual(
            ifc.parse_allow(["png", "gif,bmp"]), {"png", "gif", "bmp"}
        )

    def test_jpeg_spelling_means_jpg(self):
        self.assertEqual(ifc.parse_allow(["jpeg"]), {"jpg"})

    def test_tif_spelling_means_tiff(self):
        self.assertEqual(ifc.parse_allow(["tif"]), {"tiff"})

    def test_case_insensitive(self):
        self.assertEqual(ifc.parse_allow(["PNG,JPG"]), {"png", "jpg"})

    def test_spaces_around_names(self):
        self.assertEqual(ifc.parse_allow(["png, gif"]), {"png", "gif"})

    def test_unknown_format_raises(self):
        with self.assertRaises(ValueError) as ctx:
            ifc.parse_allow(["png,zip"])
        self.assertEqual(str(ctx.exception), "zip")

    def test_empty_part_raises(self):
        with self.assertRaises(ValueError):
            ifc.parse_allow(["png,"])


class CheckFormatTests(unittest.TestCase):
    def test_allowed_format_passes(self):
        self.assertEqual(ifc.check_format("PNG", {"png", "jpg"}), [])

    def test_jpeg_matches_jpg_allowance(self):
        self.assertEqual(ifc.check_format("JPEG", {"jpg"}), [])

    def test_disallowed_format_fails(self):
        problems = ifc.check_format("BMP", {"png", "jpg", "webp"})
        self.assertEqual(len(problems), 1)
        self.assertIn("BMP", problems[0]["reason"])
        self.assertIn("jpg, png, webp", problems[0]["reason"])

    def test_webp_case_in_detected_name(self):
        self.assertEqual(ifc.check_format("WebP", {"webp"}), [])


class CollectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def test_good_file_passes(self):
        path = self._write("a.png", png_bytes())
        problems, skipped, info = ifc.collect_from_file(path, {"png"})
        self.assertEqual(problems, [])
        self.assertFalse(skipped)
        self.assertEqual(info, "PNG")

    def test_disallowed_file_fails(self):
        path = self._write("a.bmp", bmp_bytes())
        problems, _skipped, info = ifc.collect_from_file(
            path, {"png", "jpg", "webp"}
        )
        self.assertEqual(len(problems), 1)
        self.assertEqual(info, "BMP")

    def test_misnamed_file_detected_by_bytes(self):
        path = self._write("photo.jpg", png_bytes())
        problems, _skipped, info = ifc.collect_from_file(
            path, {"png", "jpg", "webp"}
        )
        self.assertEqual(problems, [])
        self.assertEqual(info, "PNG")

    def test_empty_file_is_a_problem(self):
        path = self._write("empty.png", b"")
        problems, _skipped, info = ifc.collect_from_file(path, {"png"})
        self.assertEqual(len(problems), 1)
        self.assertIn("empty file", problems[0]["reason"])
        self.assertIsNone(info)

    def test_text_file_is_a_problem(self):
        path = self._write("note.txt", b"this is not an image\n")
        problems, _skipped, info = ifc.collect_from_file(path, {"png"})
        self.assertEqual(len(problems), 1)
        self.assertIn("not a supported image file", problems[0]["reason"])
        self.assertIsNone(info)

    def test_missing_file_is_a_problem(self):
        problems, _skipped, info = ifc.collect_from_file(
            self.root / "gone.png", {"png"}
        )
        self.assertEqual(len(problems), 1)
        self.assertIn("cannot read file", problems[0]["reason"])
        self.assertIsNone(info)

    def test_input_file_is_not_changed(self):
        path = self._write("a.gif", gif_bytes())
        before = path.read_bytes()
        ifc.collect_from_file(path, {"png"})
        self.assertEqual(path.read_bytes(), before)


class GatherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def test_folder_walk_finds_image_files_only(self):
        self._write("a.png", png_bytes())
        self._write("b.jpg", jpeg_bytes())
        self._write("c.txt", b"not an image")
        entries, checked, _skipped = ifc.gather(
            [str(self.root)], [], True, {"png", "jpg", "webp"}
        )
        self.assertEqual(len(checked), 2)
        self.assertEqual(entries, [])

    def test_git_folder_is_never_walked(self):
        self._write(".git/hooks/a.png", png_bytes())
        self._write("a.png", png_bytes())
        _entries, checked, _skipped = ifc.gather(
            [str(self.root)], [], True, {"png"}
        )
        self.assertEqual(len(checked), 1)

    def test_no_recursive_stays_at_top_level(self):
        self._write("a.png", png_bytes())
        self._write("sub/b.png", png_bytes())
        _entries, checked, _skipped = ifc.gather(
            [str(self.root)], [], False, {"png"}
        )
        self.assertEqual(len(checked), 1)

    def test_exclude_skips_matching_files(self):
        self._write("a.png", png_bytes())
        self._write("draft-b.png", png_bytes())
        _entries, checked, _skipped = ifc.gather(
            [str(self.root)], ["draft-*"], True, {"png"}
        )
        self.assertEqual(len(checked), 1)

    def test_direct_file_is_checked_even_if_excluded(self):
        path = self._write("draft-a.png", png_bytes())
        _entries, checked, _skipped = ifc.gather(
            [str(path)], ["draft-*"], True, {"png"}
        )
        self.assertEqual(len(checked), 1)

    def test_direct_file_without_image_extension_is_checked(self):
        path = self._write("photo", png_bytes())
        entries, checked, _skipped = ifc.gather(
            [str(path)], [], True, {"png"}
        )
        self.assertEqual(len(checked), 1)
        self.assertEqual(entries, [])

    def test_uppercase_extension_is_checked(self):
        self._write("A.PNG", png_bytes())
        _entries, checked, _skipped = ifc.gather(
            [str(self.root)], [], True, {"png"}
        )
        self.assertEqual(len(checked), 1)

    def test_missing_path_raises(self):
        with self.assertRaises(FileNotFoundError):
            ifc.gather([str(self.root / "gone")], [], True, {"png"})

    def test_tiff_and_ico_walked_in_folders(self):
        self._write("a.tiff", tiff_bytes())
        self._write("b.ico", ico_bytes())
        _entries, checked, _skipped = ifc.gather(
            [str(self.root)], [], True, {"png"}
        )
        self.assertEqual(len(checked), 2)


class CLITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def test_passing_file_exits_zero(self):
        path = self._write("a.png", png_bytes())
        code, out, _err = run_cli([str(path)])
        self.assertEqual(code, 0)
        self.assertIn("a.png: PNG", out)
        self.assertIn("OK — 1 file(s) checked", out)

    def test_failing_file_exits_one(self):
        path = self._write("a.bmp", bmp_bytes())
        code, out, _err = run_cli([str(path)])
        self.assertEqual(code, 1)
        self.assertIn("FAIL", out)
        self.assertIn("BMP", out)
        self.assertIn("1 problem(s) in 1 file(s)", out)

    def test_allow_flag_changes_the_list(self):
        path = self._write("a.gif", gif_bytes())
        code, out, _err = run_cli(["--allow", "png,gif", str(path)])
        self.assertEqual(code, 0)
        self.assertIn("a.gif: GIF", out)

    def test_allow_flag_repeated(self):
        path = self._write("a.bmp", bmp_bytes())
        code, _out, _err = run_cli(
            ["--allow", "png", "--allow", "bmp", str(path)]
        )
        self.assertEqual(code, 0)

    def test_bad_allow_value_exits_two(self):
        path = self._write("a.png", png_bytes())
        code, _out, err = run_cli(["--allow", "png,zip", str(path)])
        self.assertEqual(code, 2)
        self.assertIn("unknown format in --allow: zip", err)

    def test_missing_path_exits_two(self):
        code, _out, err = run_cli([str(self.root / "gone.png")])
        self.assertEqual(code, 2)
        self.assertIn("no such file or folder", err)

    def test_no_paths_exits_two(self):
        code, _out, err = run_cli([])
        self.assertEqual(code, 2)
        self.assertIn("no image files to check", err)

    def test_empty_folder_exits_two(self):
        code, _out, err = run_cli([str(self.root)])
        self.assertEqual(code, 2)
        self.assertIn("no image files to check", err)

    def test_stdin_good_image(self):
        code, out, _err = run_cli(["--stdin"], stdin_bytes=png_bytes())
        self.assertEqual(code, 0)
        self.assertIn("<stdin>: PNG", out)

    def test_stdin_bad_image(self):
        code, out, _err = run_cli(["--stdin"], stdin_bytes=bmp_bytes())
        self.assertEqual(code, 1)
        self.assertIn("FAIL <stdin>: BMP", out)

    def test_stdin_empty(self):
        code, _out, _err = run_cli(["--stdin"], stdin_bytes=b"")
        self.assertEqual(code, 1)

    def test_json_output(self):
        path = self._write("a.bmp", bmp_bytes())
        code, out, err = run_cli(["--json", str(path)])
        self.assertEqual(code, 1)
        result = json.loads(out)
        self.assertEqual(len(result["files"]), 1)
        self.assertEqual(result["files"][0]["format"], "BMP")
        self.assertEqual(len(result["files"][0]["problems"]), 1)
        self.assertEqual(result["summary"]["checked"], 1)
        self.assertEqual(result["summary"]["problems"], 1)
        self.assertEqual(result["summary"]["allowed"], ["jpg", "png", "webp"])
        self.assertIn("Checked 1 file(s)", err)

    def test_json_output_clean_pass(self):
        path = self._write("a.png", png_bytes())
        code, out, err = run_cli(["--json", str(path)])
        self.assertEqual(code, 0)
        result = json.loads(out)
        self.assertEqual(result["files"][0]["problems"], [])
        self.assertIn("OK —", err)

    def test_version(self):
        code, out, _err = run_cli(["--version"])
        self.assertEqual(code, 0)
        self.assertIn("image-format-checker-cli 1.0.0", out)

    def test_bad_flag_exits_two(self):
        with self.assertRaises(SystemExit) as caught:
            run_cli(["--nope"])
        self.assertEqual(caught.exception.code, 2)

    def test_folder_summary_counts(self):
        self._write("a.png", png_bytes())
        self._write("b.bmp", bmp_bytes())
        self._write("c.gif", gif_bytes())
        code, out, _err = run_cli([str(self.root)])
        self.assertEqual(code, 1)
        self.assertIn("Checked 3 file(s), 2 problem(s) in 2 file(s).", out)

    def test_real_fixture_files(self):
        examples = REPO_ROOT / "examples"
        code, out, _err = run_cli([str(examples)])
        self.assertEqual(code, 1)
        self.assertIn("Checked 9 file(s), 4 problem(s) in 4 file(s).", out)
        self.assertIn("examples/good.png: PNG", out)
        self.assertIn("examples/good.jpg: JPEG", out)
        self.assertIn("examples/good.webp: WebP", out)
        self.assertIn("examples/misnamed.jpg: PNG", out)
        self.assertIn("examples/photo.bmp: BMP", out)


class BundledExamplesTests(unittest.TestCase):
    def test_run_example_matches_sample_output(self):
        result = subprocess.run(
            ["sh", "examples/run-example.sh"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0)
        expected = (REPO_ROOT / "examples" / "sample-output.md").read_text(
            encoding="utf-8"
        )
        self.assertEqual(result.stdout, expected)

    def test_readme_quotes_match_real_runs(self):
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        cases = [
            (
                ["examples/good.png"],
                "examples/good.png: PNG\n"
                "OK — 1 file(s) checked, all images are in an allowed format.\n",
            ),
            (
                ["examples/photo.bmp"],
                "FAIL examples/photo.bmp: BMP — not an allowed format "
                "(BMP; allowed: jpg, png, webp)\n"
                "Checked 1 file(s), 1 problem(s) in 1 file(s).\n",
            ),
            (
                ["--allow", "png,jpg,webp,gif", "examples/photo.gif"],
                "examples/photo.gif: GIF\n"
                "OK — 1 file(s) checked, all images are in an allowed format.\n",
            ),
            (
                ["examples/misnamed.jpg"],
                "examples/misnamed.jpg: PNG\n"
                "OK — 1 file(s) checked, all images are in an allowed format.\n",
            ),
            (
                ["examples/empty.png"],
                "FAIL examples/empty.png — cannot read format (empty file)\n"
                "Checked 1 file(s), 1 problem(s) in 1 file(s).\n",
            ),
        ]
        old_cwd = os.getcwd()
        try:
            os.chdir(REPO_ROOT)
            for argv, expected in cases:
                code, out, _err = run_cli(argv)
                self.assertIn(expected, readme)
                self.assertEqual(out, expected)
        finally:
            os.chdir(old_cwd)


class HygieneTests(unittest.TestCase):
    def _repo_files(self):
        for path in REPO_ROOT.rglob("*"):
            if not path.is_file():
                continue
            parts = path.relative_to(REPO_ROOT).parts
            if ".git" in parts or "__pycache__" in parts:
                continue
            if parts[0] == "tests":
                continue
            yield path

    def test_no_placeholder_text(self):
        banned = ["TODO", "FIXME", "XXX", "coming soon", "lorem"]
        hits = []
        for path in self._repo_files():
            text = path.read_text(errors="ignore")
            for word in banned:
                if word in text:
                    hits.append(f"{path.relative_to(REPO_ROOT)}: {word}")
        self.assertEqual(hits, [])

    def test_no_absolute_paths(self):
        hits = []
        for path in self._repo_files():
            text = path.read_text(errors="ignore")
            for needle in ("/home/", "/Users/", "C:\\"):
                if needle in text:
                    hits.append(str(path.relative_to(REPO_ROOT)))
        self.assertEqual(hits, [])

    def test_stdlib_imports_only(self):
        allowed = ALLOWED_STDLIB | {
            "io",
            "struct",
            "subprocess",
            "tempfile",
            "unittest",
            "contextlib",
            "image_format_checker",
        }
        hits = []
        for path in list((REPO_ROOT / "src").glob("*.py")) + list(
            (REPO_ROOT / "tests").glob("*.py")
        ):
            text = path.read_text(encoding="utf-8")
            for line in text.splitlines():
                line = line.strip()
                for prefix in ("import ", "from "):
                    if line.startswith(prefix):
                        name = line[len(prefix):].split()[0].split(".")[0]
                        if name not in allowed:
                            hits.append(f"{path.name}: {line}")
        self.assertEqual(hits, [])

    def test_env_is_first_line_of_gitignore(self):
        lines = (REPO_ROOT / ".gitignore").read_text(
            encoding="utf-8"
        ).splitlines()
        self.assertTrue(lines)
        self.assertEqual(lines[0], ".env")

    def test_ci_file_runs_the_test_file(self):
        ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("python3 tests/test_image_format_checker.py", ci)
        self.assertIn("actions/checkout@v4", ci)
        self.assertIn("actions/setup-python@v5", ci)
        self.assertIn('python-version: "3.12"', ci)


if __name__ == "__main__":
    unittest.main()
