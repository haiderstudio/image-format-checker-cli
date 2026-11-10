#!/bin/sh
# Check the bundled examples. The failing runs exit 1 on purpose,
# so each one ends with "|| true"; the script itself ends with
# exit 0 so it can be run as a demo. Run from the repo root:
# sh examples/run-example.sh
cd "$(dirname "$0")/.."
echo "== good.png: an allowed format, passes =="
python3 src/image_format_checker.py examples/good.png || true
echo
echo "== photo.gif: GIF is not allowed by default =="
python3 src/image_format_checker.py examples/photo.gif || true
echo
echo "== misnamed.jpg: PNG bytes under a .jpg name, still a PNG =="
python3 src/image_format_checker.py examples/misnamed.jpg || true
echo
echo "== examples/: a folder walk, four problems =="
python3 src/image_format_checker.py examples/ || true
