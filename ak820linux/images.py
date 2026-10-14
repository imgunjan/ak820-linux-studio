"""Local picture and GIF conversion for 128x128 RGB565 little-endian TFT."""

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageSequence

SCREEN = (128, 128)


def convert_size(img: Image.Image, fit: str = 'cover') -> Image.Image:
    rgba = img.convert('RGBA')
    rgb = Image.new('RGBA', rgba.size, '#000000')
    rgb.alpha_composite(rgba)
    if fit == 'contain':
        result = ImageOps.contain(rgb.convert('RGB'), SCREEN, Image.Resampling.LANCZOS)
        canvas = Image.new('RGB', SCREEN, '#000000')
        canvas.paste(result, ((128 - result.width) // 2, (128 - result.height) // 2))
        return canvas
    if fit == 'stretch':
        return rgb.convert('RGB').resize(SCREEN, Image.Resampling.LANCZOS)
    return ImageOps.fit(rgb.convert('RGB'), SCREEN, Image.Resampling.LANCZOS, centering=(.5, .5))


def rgb565(img: Image.Image) -> bytes:
    if img.size != SCREEN:
        raise ValueError('Image is not 128 x 128')
    out = bytearray(32768)
    pixels = img.convert('RGB')
    flattened = pixels.get_flattened_data() if hasattr(pixels, 'get_flattened_data') else pixels.getdata()
    for i, (r, g, b) in enumerate(flattened):
        v = ((r & 0xf8) << 8) | ((g & 0xfc) << 3) | (b >> 3)
        out[2 * i] = v & 255
        out[2 * i + 1] = (v >> 8) & 255
    return bytes(out)


def from_path(path: str, fit: str = 'cover', max_frames: int = 60):
    """Return list RGB565 frames, delays, preview image. Pillow composites GIFs on seek."""
    if not 1 <= max_frames <= 255:
        raise ValueError('max_frames must be between 1 and 255')
    frames, delays = [], []
    preview = None
    with Image.open(path) as im:
        if im.width * im.height > 40_000_000:
            raise ValueError('Image dimensions exceed safety limit')
        for item in ImageSequence.Iterator(im):
            result = convert_size(item.copy().convert('RGBA'), fit)
            preview = preview or result
            frames.append(rgb565(result))
            delays.append(max(20, int(item.info.get('duration', 100) or 100)))
            if len(frames) >= max_frames:
                break
    if len(frames) == 0:
        raise ValueError('No valid frames')
    return frames, delays if len(frames) > 1 else None, preview


def text_card(message: str, fg: str = '#ffffff', bg: str = '#101827') -> Image.Image:
    img = Image.new('RGB', SCREEN, bg)
    d = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=16)
    words = message.strip().split()
    lines = []
    line = ''
    for word in words:
        trial = f'{line} {word}'.strip()
        if d.textbbox((0, 0), trial, font=font)[2] > 118 and line:
            lines.append(line)
            line = word
        else:
            line = trial
    if line:
        lines.append(line)
    lines = lines[:5] or ['Linux']
    h = 20 * len(lines)
    for n, line in enumerate(lines):
        width = d.textbbox((0, 0), line, font=font)[2]
        d.text(((128 - width) / 2, (128 - h) / 2 + n * 20), line, font=font, fill=fg)
    return img
