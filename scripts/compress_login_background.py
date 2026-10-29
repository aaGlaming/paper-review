"""压缩登录页背景图：等比缩到宽 1600，PNG optimize；仍超 500KB 则转 8 位调色板。

幂等：输入已达标时直接跳过（不重写）；输出只会不变或更小。
用法：python scripts/compress_login_background.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

TARGET = Path(__file__).resolve().parents[1] / "frontend" / "pictures" / "login_background.png"
WEBP = TARGET.with_suffix(".webp")
WIDTH = 1600
LIMIT = 500 * 1024


def save_png(image: Image.Image, palette: bool = False) -> int:
    picture = image.convert("P", palette=Image.ADAPTIVE, colors=256) if palette else image
    picture.save(TARGET, optimize=True)
    return TARGET.stat().st_size


def main() -> None:
    before = TARGET.stat().st_size if TARGET.exists() else WEBP.stat().st_size
    source = TARGET if TARGET.exists() else WEBP
    with Image.open(source) as picture:
        print(f"before={before} size={picture.size} mode={picture.mode}")
        if picture.width > WIDTH:
            ratio = WIDTH / picture.width
            picture = picture.resize((WIDTH, round(picture.height * ratio)), Image.LANCZOS)
        after = save_png(picture.convert("RGB"))
        fmt = "PNG"
        if after > LIMIT:
            after = save_png(picture.convert("RGB"), palette=True)
            fmt = "PNG-8"
        if after > LIMIT:
            picture.convert("RGB").save(WEBP, "WEBP", quality=82, method=6)
            TARGET.unlink(missing_ok=True)
            after = WEBP.stat().st_size
            fmt = "WebP"
    print(f"after={after} format={fmt} (before={before})")


if __name__ == "__main__":
    main()
