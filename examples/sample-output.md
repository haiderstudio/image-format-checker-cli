== good.png: an allowed format, passes ==
examples/good.png: PNG
OK — 1 file(s) checked, all images are in an allowed format.

== photo.gif: GIF is not allowed by default ==
FAIL examples/photo.gif: GIF — not an allowed format (GIF; allowed: jpg, png, webp)
Checked 1 file(s), 1 problem(s) in 1 file(s).

== misnamed.jpg: PNG bytes under a .jpg name, still a PNG ==
examples/misnamed.jpg: PNG
OK — 1 file(s) checked, all images are in an allowed format.

== examples/: a folder walk, four problems ==
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
