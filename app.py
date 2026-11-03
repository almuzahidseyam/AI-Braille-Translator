from io import BytesIO
import streamlit as st
from braille import DecodeError, decode_unicode, load_image, read_grid, example_image

st.set_page_config(page_title='Braille reader · Research prototype', layout='centered')
st.title('Braille reader')
st.write('Read a calibrated six-dot grid, or decode supported Unicode Braille.')
st.caption('Research prototype for a limited English alphabet subset. Arbitrary camera photos, embossed paper, contractions and other languages are not supported.')

image_tab, text_tab = st.tabs(['Printed grid', 'Unicode Braille'])
with image_tab:
    st.write('Use dark printed dots on a plain white background. Crop to an exact rectangular grid with equal-size cells, including blank cells for spaces.')
    with st.expander('Grid alignment and example'):
        st.write('Within each cell, dot columns must sit at ⅓ and ⅔ of its width; dot rows at ¼, ½ and ¾ of its height. The preview marks the six sampled regions. Check every region against your source before relying on the result.')
        example = example_image()
        st.image(example, caption='Supported example: hello · 1 row × 5 columns')
        data = BytesIO(); example.save(data, format='PNG')
        st.download_button('Download example grid', data.getvalue(), 'hello-braille.png', 'image/png')
    upload = st.file_uploader('PNG or JPEG grid · up to 10 MiB / 12 million pixels', type=['png', 'jpg', 'jpeg'])
    first, second = st.columns(2)
    rows = first.number_input('Rows', min_value=1, max_value=20, value=1, step=1)
    columns = second.number_input('Cells per row', min_value=1, max_value=80, value=5, step=1)
    threshold = st.slider('Dark-dot threshold', min_value=32, max_value=224, value=128)
    if upload is not None:
        try:
            image = load_image(upload.getvalue())
            st.image(image, caption='Your source image')
            if st.button('Read calibrated grid', type='primary'):
                result = read_grid(image, rows, columns, threshold)
                st.image(result.overlay, caption='Review alignment: cell borders and sampled dot regions')
                if result.problems:
                    st.warning('No text decoded. The grid is ambiguous or uses unsupported characters.')
                    for problem in result.problems[:12]: st.text(problem)
                    if len(result.problems) > 12: st.caption(f'{len(result.problems) - 12} more uncertain regions.')
                else:
                    st.subheader('Candidate text — verify against the source')
                    st.text(result.text)
                    st.download_button('Export candidate text', ('Candidate transcription from a calibrated grid; verify against the source.\n\n' + result.text).encode(), 'braille-candidate.txt', 'text/plain')
                with st.expander('Detected cell patterns'):
                    st.text(result.unicode)
        except DecodeError as error:
            st.error(str(error))

with text_tab:
    st.write('Supports a–z, spaces, newlines, single-letter capitals, integer digits after a number indicator, and a letter indicator after digits. Input must be uncontracted English. Punctuation, eight-dot cells and capital-word/passage indicators are rejected. Contracted Braille can share these same cells and cannot be automatically identified; do not use it here.')
    value = st.text_area('Unicode Braille input', placeholder='⠓⠑⠇⠇⠕ ⠺⠕⠗⠇⠙', max_chars=5000)
    if st.button('Decode characters'):
        try:
            decoded = decode_unicode(value)
            st.subheader('Decoded text')
            st.text(decoded)
            st.download_button('Download text', decoded.encode(), 'braille-text.txt', 'text/plain')
        except DecodeError as error:
            st.warning(str(error))
st.caption('Images and text are processed on the machine running this app. No translation or speech service receives them. No results are written to a database.')
