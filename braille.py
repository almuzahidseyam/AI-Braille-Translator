"""Deterministic six-dot alphabet decoder and calibrated printed-grid reader.

This is not OCR for arbitrary photos, contracted braille, or embossed paper.
"""
from dataclasses import dataclass
from io import BytesIO
import warnings
from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError

# Unicode six-dot bits: left top/middle/bottom = 1/2/3, right = 4/5/6.
LETTERS = dict(zip([1, 3, 9, 25, 17, 11, 27, 19, 10, 26, 5, 7, 13, 29, 21, 15, 31, 23, 14, 30, 37, 39, 58, 45, 61, 53], 'abcdefghijklmnopqrstuvwxyz'))
MASKS = {letter: mask for mask, letter in LETTERS.items()}
MAX_PIXELS = 12_000_000
MAX_BYTES = 10 * 1024 * 1024


class DecodeError(ValueError):
    pass


def decode_unicode(value):
    if not isinstance(value, str) or len(value) > 5000:
        raise DecodeError('Use at most 5,000 Braille characters.')
    output = []
    numeric = False
    capital = False
    pending_number = False
    letter_indicator = False
    for index, char in enumerate(value):
        if char in (' ', '\n', '\t', '\u2800'):
            if capital or pending_number or letter_indicator:
                raise DecodeError(f'Incomplete indicator before cell {index + 1}.')
            output.append('\n' if char == '\n' else ' ')
            numeric = False
            continue
        mask = ord(char) - 0x2800
        if not 0 <= mask <= 63:
            raise DecodeError(f'Cell {index + 1} is not a supported six-dot Braille character.')
        if mask == 32:  # Single capital indicator.
            if capital or pending_number or letter_indicator:
                raise DecodeError('Repeated or combined indicators are unsupported.')
            capital = True
            numeric = False
            continue
        if mask == 60:  # Numeric indicator, dots 3456.
            if capital or pending_number or letter_indicator:
                raise DecodeError('Repeated or combined indicators are unsupported.')
            pending_number = True
            numeric = True
            continue
        if mask == 48:  # Grade-one symbol indicator for a letter after digits.
            if capital or pending_number or letter_indicator or not numeric:
                raise DecodeError('A letter indicator is supported only after digits.')
            letter_indicator = True
            numeric = False
            continue
        letter = LETTERS.get(mask)
        if letter is None:
            raise DecodeError(f'Cell {index + 1} uses punctuation, a contraction or an unsupported pattern.')
        if pending_number and letter not in 'abcdefghij':
            raise DecodeError(f'Expected a digit after the number indicator at cell {index + 1}.')
        if numeric and letter in 'abcdefghij':
            output.append(str(('abcdefghij'.index(letter) + 1) % 10))
        else:
            numeric = False
            output.append(letter.upper() if capital else letter)
        capital = pending_number = letter_indicator = False
    if capital or pending_number or letter_indicator:
        raise DecodeError('The input ends with an incomplete indicator.')
    if not ''.join(output).strip():
        raise DecodeError('No supported letters or digits were found.')
    return ''.join(output)


def load_image(data):
    if not isinstance(data, bytes) or len(data) > MAX_BYTES:
        raise DecodeError('Use a PNG or JPEG no larger than 10 MiB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as original:
                if original.format not in ('PNG', 'JPEG') or original.width * original.height > MAX_PIXELS:
                    raise DecodeError('Use a PNG or JPEG with no more than 12 million pixels.')
                original.load()
                image = ImageOps.exif_transpose(original)
                # Transparency becomes white rather than an artificial black dot.
                if image.mode == 'RGBA' or 'transparency' in image.info:
                    rgba = image.convert('RGBA')
                    background = Image.new('RGBA', rgba.size, 'white')
                    background.alpha_composite(rgba)
                    image = background
                return image.convert('RGB')
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise DecodeError('The image is corrupt, unsupported or too large.') from None


@dataclass
class GridResult:
    unicode: str
    text: str | None
    problems: list[str]
    overlay: Image.Image


def read_grid(image, rows, columns, threshold=128):
    if type(rows) is not int or type(columns) is not int or not 1 <= rows <= 20 or not 1 <= columns <= 80 or rows * columns > 1000:
        raise DecodeError('Use 1–20 rows, 1–80 columns, and at most 1,000 cells.')
    if type(threshold) is not int or not 32 <= threshold <= 224:
        raise DecodeError('Threshold must be between 32 and 224.')
    width, height = image.size
    if width * height > MAX_PIXELS or width / columns < 24 or height / rows < 36:
        raise DecodeError('Each cell needs at least 24×36 pixels; image limit is 12 million pixels.')
    # Bound processing after validating the original dimensions.
    image = image.copy()
    image.thumbnail((2400, 2400))
    gray = image.convert('L')
    overlay = image.convert('RGB')
    draw = ImageDraw.Draw(overlay)
    cell_w, cell_h = image.width / columns, image.height / rows
    if cell_w < 24 or cell_h < 36:
        raise DecodeError('Too many cells for the processing resolution. Split the page into smaller images.')
    lines, problems = [], []
    for row in range(rows):
        line = []
        for col in range(columns):
            mask, occupied = 0, 0
            x0, y0 = col * cell_w, row * cell_h
            radius = min(cell_w / 12, cell_h / 16)
            for bit in range(6):
                x = x0 + cell_w * (1 / 3 if bit < 3 else 2 / 3)
                y = y0 + cell_h * ((bit % 3 + 1) / 4)
                box = (round(x-radius), round(y-radius), round(x+radius), round(y+radius))
                pixels = gray.crop(box)
                dark = sum(pixels.histogram()[:threshold])
                occupied += dark
                fraction = dark / (pixels.width * pixels.height)
                if fraction >= .55:
                    mask |= 1 << bit
                elif fraction > .10:
                    problems.append(f'Row {row+1}, cell {col+1}, dot {bit+1}: ambiguous contrast or alignment.')
                draw.rectangle(box, outline='#477a64' if fraction >= .55 else '#a4abb3', width=1)
            cell_box = (round(x0), round(y0), round(x0+cell_w), round(y0+cell_h))
            cell = gray.crop(cell_box)
            total_dark = sum(cell.histogram()[:threshold])
            if total_dark - occupied > cell.width * cell.height * .02:
                problems.append(f'Row {row+1}, cell {col+1}: marks outside the expected dot regions.')
            draw.rectangle(cell_box, outline='#b9b1c7', width=1)
            line.append(chr(0x2800 + mask))
        lines.append(''.join(line))
    value = '\n'.join(lines)
    text = None
    if not problems:
        try:
            text = decode_unicode(value)
        except DecodeError as error:
            problems.append(str(error))
    return GridResult(value, text, problems, overlay)


def example_image():
    # A reproducible supported input: five 60x80 cells containing "hello".
    image = Image.new('RGB', (300, 80), 'white')
    draw = ImageDraw.Draw(image)
    for col, letter in enumerate('hello'):
        for bit in range(6):
            if MASKS[letter] & (1 << bit):
                x = col * 60 + (20 if bit < 3 else 40)
                y = (bit % 3 + 1) * 20
                draw.ellipse((x-4, y-4, x+4, y+4), fill='black')
    return image
