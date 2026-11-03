from io import BytesIO
from pathlib import Path
import sys
import pytest
from PIL import Image, ImageDraw
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from braille import decode_unicode, read_grid, load_image, example_image, DecodeError, MAX_BYTES


def test_full_alphabet_and_real_phrases():
    assert decode_unicode('⠁⠃⠉⠙⠑⠋⠛⠓⠊⠚⠅⠇⠍⠝⠕⠏⠟⠗⠎⠞⠥⠧⠺⠭⠽⠵') == 'abcdefghijklmnopqrstuvwxyz'
    assert decode_unicode('⠓⠑⠇⠇⠕ ⠺⠕⠗⠇⠙') == 'hello world'
    assert decode_unicode('⠠⠓⠑⠇⠇⠕\n⠼⠁⠃⠉⠙⠑⠋⠛⠓⠊⠚') == 'Hello\n1234567890'
    assert decode_unicode('⠼⠁⠁⠰⠃') == '11b'


@pytest.mark.parametrize('value', ['', '  ', 'hello', '⠠', '⠼', '⠼⠅', '⠠⠠⠁', '⣿', '⠂', '⠠ ⠁', '⠼⠁⠰', '⠰⠁', '⠁' * 5001])
def test_unsupported_and_incomplete_input_has_no_invented_translation(value):
    with pytest.raises(DecodeError): decode_unicode(value)


def test_actual_image_grid_decodes_hello():
    result = read_grid(example_image(), 1, 5)
    assert result.text == 'hello'
    assert result.unicode == '⠓⠑⠇⠇⠕'
    assert result.problems == []


def test_same_number_of_dots_in_different_positions_produces_different_letters():
    def image_at(points):
        image = Image.new('RGB', (60, 80), 'white'); draw = ImageDraw.Draw(image)
        for x, y in points: draw.ellipse((x-4,y-4,x+4,y+4),fill='black')
        return image
    assert read_grid(image_at([(20,20),(20,40)]), 1, 1).text == 'b'
    assert read_grid(image_at([(20,20),(40,20)]), 1, 1).text == 'c'


def test_misaligned_and_noisy_images_fail_closed():
    image = example_image(); ImageDraw.Draw(image).rectangle((0,0,15,25), fill='black')
    result = read_grid(image, 1, 5)
    assert result.text is None and result.problems
    blank = read_grid(Image.new('RGB', (300,80), 'white'), 1, 5)
    assert blank.text is None
    assert read_grid(example_image(), 1, 4).text is None


def test_ambiguous_dot_never_becomes_exportable_text():
    image = Image.new('RGB', (60,80), 'white')
    ImageDraw.Draw(image).rectangle((16,16,19,20), fill='black')
    result = read_grid(image, 1, 1)
    assert result.text is None and any('ambiguous' in message for message in result.problems)


@pytest.mark.parametrize('rows,columns,threshold', [(0,5,128),(1,0,128),(21,5,128),(20,80,128),(True,5,128),(1,5,0),(1,5,128.5)])
def test_grid_bounds(rows,columns,threshold):
    with pytest.raises(DecodeError): read_grid(example_image(), rows, columns, threshold)


def test_safe_image_loading_and_transparency():
    data=BytesIO(); example_image().save(data,format='PNG')
    assert load_image(data.getvalue()).size == (300,80)
    image=Image.new('RGBA',(60,80),(0,0,0,0)); data=BytesIO(); image.save(data,format='PNG')
    assert load_image(data.getvalue()).getpixel((0,0)) == (255,255,255)
    for value in [b'not an image', b'x'*(MAX_BYTES+1)]:
        with pytest.raises(DecodeError): load_image(value)
    large=Image.new('1',(4000,3100)); data=BytesIO(); large.save(data,format='PNG')
    with pytest.raises(DecodeError): load_image(data.getvalue())


def test_ui_uses_decoded_characters_and_rejects_unknowns():
    from streamlit.testing.v1 import AppTest
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run()
    assert not app.exception
    app.text_area[0].set_value('⠓⠑⠇⠇⠕'); app.button[0].click().run()
    assert not app.exception and any(text.value == 'hello' for text in app.text)
    app.text_area[0].set_value('⣿'); app.button[0].click().run()
    assert not app.exception and app.warning
    assert not any(text.value == 'hello' for text in app.text)
