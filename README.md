# Braille reader

A deterministic research prototype that decodes a limited uncontracted English
six-dot alphabet from Unicode cells or a carefully calibrated printed grid.
The repository keeps its original name, `AI-Braille-Translator`, but the current
reader does not use an AI model.

The previous implementation counted contours and returned unrelated preset
sentences. That behavior has been removed. Results now depend on the positions
of the dots in each cell. An uncertain grid or unsupported pattern produces no
exportable text, rather than a plausible-looking invented translation.

## Supported input

- Lowercase a–z, spaces and newlines.
- A single capital indicator before one letter.
- Integer digits after a numeric indicator; a letter indicator after digits.
- For images: dark printed dots on white, with straight, equal-sized cells in a
  rectangular grid. No automatic page segmentation or perspective correction.

This is **not** a complete UEB implementation. Punctuation, eight-dot codes,
capital-word/passage indicators, other languages and arbitrary embossed-paper
photos are unsupported. Contracted Braille can reuse alphabetic cells and cannot
be detected automatically; only supply uncontracted English input. It is not a
replacement for an established accessible transcription service.

## Run

Use Python 3.12 or 3.13:

```sh
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt -c constraints.txt
python -m streamlit run app.py --server.address=127.0.0.1
```

No API keys, model downloads, translator service or speech service are required.
Images/text remain on the machine running Streamlit. There are no remote media
assets, analytics calls from application code, or stored scan-history database.
For local privacy, keep the server bound to loopback; on a hosted deployment,
uploads necessarily go to that host. Streamlit's own telemetry can be disabled
with `--browser.gatherUsageStats=false`.

## Read a printed grid

1. Download the app's generated **hello** example and try 1 row, 5 cells per row.
2. Crop your input to exact equal cells, including blank cells for word spaces.
3. Inside each cell, put dot columns at ⅓ and ⅔ of cell width, and dot rows at ¼,
   ½ and ¾ of cell height. This alignment is a requirement, not something the
   reader discovers automatically.
4. Set rows and cells per row, then choose **Read calibrated grid**.
5. Check the source against the preview's six sampled regions and the candidate
   text before exporting it. Even an accepted grid can be miscalibrated; exports
   carry a candidate-transcription label.

Each sampled region is classified as dark, light or ambiguous. Significant ink
outside the regions is rejected. The threshold can be adjusted for a clean scan;
it cannot make an arbitrary photo supported. Input is capped at 10 MiB and 12
million pixels, with at most 1,000 cells. Invalid images, empty pages, incomplete
indicators and unsupported characters produce explicit errors.

The **Unicode Braille** tab reads actual cell patterns. For example,
`⠓⠑⠇⠇⠕ ⠺⠕⠗⠇⠙` decodes to `hello world`. It does not translate between languages.

## Verify

```sh
python -m pip install -r requirements-dev.txt -c constraints.txt
python -m pytest -q
python -m pip_audit -r constraints.txt --no-deps --disable-pip
```

Tests cover all 26 letters, digits, capitals, incomplete/unsupported input,
transparent/corrupt/oversized images, grid alignment and actual image decoding.
A regression fixture gives two cells the same number of dots in different
positions and verifies different letters, preventing the old count-based fake
translation. Streamlit tests verify visible success and error states. CI repeats
tests and audits before changes are considered ready.

Implementation: `braille.py` contains image validation and deterministic decoding;
`app.py` contains the interface. Dependencies are constrained to tested versions.

Braille context: [BANA guidance on uncontracted Braille and indicators](https://www.brailleauthority.org/signage/index.html).
The application implements only the explicitly listed subset, not that complete standard.
