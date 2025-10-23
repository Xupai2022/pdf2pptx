# PDF to PPTX Converter

A professional tool to convert PDF files to editable PowerPoint presentations.

## Architecture Overview

The system is divided into five main modules:

```
PDF Parser → Layout Analyzer → Element Rebuilder → Style Mapper → PPTX Generator
```

### Modules

1. **PDF Parser Layer** - Extracts text blocks, images, vectors, fonts, and layout information
2. **Layout Analyzer Layer** - Analyzes page structure (titles, paragraphs, charts, headers/footers)
3. **Element Rebuilder Layer** - Converts to unified intermediate representation
4. **Style Mapper Layer** - Maps PDF styles to PowerPoint attributes
5. **PPTX Generator Layer** - Outputs editable PPTX files

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Convert a single PDF
python main.py input.pdf output.pptx

# With options
python main.py input.pdf output.pptx --dpi 300 --preserve-layout
```

## Project Structure

```
pdf2pptx/
├── main.py                 # Entry point
├── requirements.txt        # Dependencies
├── README.md              # Documentation
├── tests/                 # Test files
│   └── test_sample.pdf    # Sample PDF for testing
├── output/                # Generated PPTX files
├── src/
│   ├── __init__.py
│   ├── parser/            # PDF parsing module
│   │   ├── __init__.py
│   │   ├── pdf_parser.py
│   │   └── element_extractor.py
│   ├── analyzer/          # Layout analysis module
│   │   ├── __init__.py
│   │   ├── layout_analyzer.py
│   │   └── structure_detector.py
│   ├── rebuilder/         # Element rebuilding module
│   │   ├── __init__.py
│   │   ├── slide_model.py
│   │   └── coordinate_mapper.py
│   ├── mapper/            # Style mapping module
│   │   ├── __init__.py
│   │   ├── style_mapper.py
│   │   └── font_mapper.py
│   └── generator/         # PPTX generation module
│       ├── __init__.py
│       ├── pptx_generator.py
│       └── element_renderer.py
└── config/
    └── config.yaml        # Configuration file
```

## Features

- ✅ Extract text with positioning and font information
- ✅ Extract images and preserve quality
- ✅ Analyze page layout and structure
- ✅ Intelligent title/content detection
- ✅ Style preservation (fonts, colors, alignments)
- ✅ Generate editable PPTX files

## Requirements

- Python 3.8+
- PyMuPDF (fitz)
- python-pptx
- Pillow
- pdfplumber

## License

MIT License
