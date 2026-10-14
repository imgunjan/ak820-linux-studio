"""Local picture and GIF conversion for 128x128 RGB565 little-endian TFT."""

from dataclasses import dataclass
import math

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps, ImageSequence

SCREEN = (128, 128)


@dataclass
class PreparedImage:
    frames: list[bytes]
    delays: list[int] | None
    previews: list[Image.Image]
    truncated: bool = False
    timing_limited: bool = False


def convert_size(
    img: Image.Image, fit: str = "cover", *, rotation: int = 0, brightness: float = 1.0
) -> Image.Image:
    if fit not in ("cover", "contain", "stretch"):
        raise ValueError("Fit must be cover, contain, or stretch")
    if rotation not in (0, 90, 180, 270):
        raise ValueError("Rotation must be 0, 90, 180, or 270 degrees clockwise")
    if not math.isfinite(brightness) or not 0 <= brightness <= 2:
        raise ValueError("Brightness must be between 0 and 2")
    rgba = ImageOps.exif_transpose(img).convert("RGBA")
    if rotation:
        rgba = rgba.rotate(-rotation, expand=True)
    rgb = Image.new("RGBA", rgba.size, "#000000")
    rgb.alpha_composite(rgba)
    if fit == "contain":
        result = ImageOps.contain(rgb.convert("RGB"), SCREEN, Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", SCREEN, "#000000")
        canvas.paste(result, ((128 - result.width) // 2, (128 - result.height) // 2))
        result = canvas
    elif fit == "stretch":
        result = rgb.convert("RGB").resize(SCREEN, Image.Resampling.LANCZOS)
    else:
        result = ImageOps.fit(
            rgb.convert("RGB"), SCREEN, Image.Resampling.LANCZOS, centering=(0.5, 0.5)
        )
    return ImageEnhance.Brightness(result).enhance(brightness)


def rgb565(img: Image.Image) -> bytes:
    if img.size != SCREEN:
        raise ValueError("Image is not 128 x 128")
    out = bytearray(32768)
    pixels = img.convert("RGB")
    flattened = (
        pixels.get_flattened_data()
        if hasattr(pixels, "get_flattened_data")
        else pixels.getdata()
    )
    for i, (r, g, b) in enumerate(flattened):
        v = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
        out[2 * i] = v & 255
        out[2 * i + 1] = (v >> 8) & 255
    return bytes(out)


def prepare_image(
    path: str,
    fit: str = "cover",
    max_frames: int = 60,
    *,
    rotation: int = 0,
    brightness: float = 1.0,
    speed: float = 1.0,
) -> PreparedImage:
    """Prepare upload data and every preview frame, with matching playback timing."""
    if not isinstance(max_frames, int) or not 1 <= max_frames <= 255:
        raise ValueError("max_frames must be between 1 and 255")
    if not math.isfinite(speed) or not 0.25 <= speed <= 4:
        raise ValueError("GIF speed must be between 0.25 and 4")
    frames, delays, previews = [], [], []
    truncated = timing_limited = False
    with Image.open(path) as im:
        if im.width * im.height > 40_000_000:
            raise ValueError("Image dimensions exceed safety limit")
        for index, item in enumerate(ImageSequence.Iterator(im)):
            if index == max_frames:
                truncated = True
                break
            if item.width * item.height > 40_000_000:
                raise ValueError("Image dimensions exceed safety limit")
            result = convert_size(item, fit, rotation=rotation, brightness=brightness)
            previews.append(result)
            frames.append(rgb565(result))
            requested_delay = (
                max(20, int(item.info.get("duration", 100) or 100)) / speed
            )
            # The existing keyboard header stores a delay in 2 ms units (1..255).
            timing_limited |= not 2 <= requested_delay <= 510
            delays.append(2 * max(1, min(255, round(requested_delay / 2))))
    if not frames:
        raise ValueError("No valid frames")
    return PreparedImage(
        frames,
        delays if len(frames) > 1 else None,
        previews,
        truncated,
        timing_limited and len(frames) > 1,
    )


def from_path(path: str, fit: str = "cover", max_frames: int = 60, **options):
    """Compatibility wrapper returning frames, delays, and the first preview."""
    prepared = prepare_image(path, fit, max_frames, **options)
    return prepared.frames, prepared.delays, prepared.previews[0]


def text_card(
    message: str,
    fg: str = "#ffffff",
    bg: str = "#101827",
    *,
    font_size: int = 16,
    alignment: str = "center",
) -> Image.Image:
    if not isinstance(font_size, int) or not 8 <= font_size <= 32:
        raise ValueError("Font size must be between 8 and 32")
    if alignment not in ("left", "center", "right"):
        raise ValueError("Alignment must be left, center, or right")
    img = Image.new("RGB", SCREEN, bg)
    d = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=font_size)

    def width(text):
        box = d.textbbox((0, 0), text, font=font)
        return box[2] - box[0]

    lines = []
    for paragraph in (message.strip() or "Linux").splitlines():
        line = ""
        for word in paragraph.split():
            trial = f"{line} {word}".strip()
            if line and width(trial) > 118:
                lines.append(line)
                line = ""
            # Break long words too, so they cannot run off the small display.
            for char in (" " if line else "") + word:
                if line and width(line + char) > 118:
                    lines.append(line)
                    line = ""
                line += char
        lines.append(line)
    line_height = font_size + 4
    max_lines = 118 // line_height
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        while lines[-1] and width(lines[-1] + "...") > 118:
            lines[-1] = lines[-1][:-1]
        lines[-1] += "..."
    h = line_height * len(lines)
    for n, line in enumerate(lines):
        box = d.textbbox((0, 0), line, font=font)
        x = {"left": 5, "center": (128 - width(line)) / 2, "right": 123 - width(line)}[
            alignment
        ]
        y = (128 - h) / 2 + n * line_height
        d.text((x - box[0], y - box[1]), line, font=font, fill=fg)
    return img
