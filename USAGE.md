# PDF to PPTX Converter - Usage Guide

## Quick Start

### Basic Usage

Convert a PDF to PowerPoint:

```bash
python main.py input.pdf output.pptx
```

### With Options

```bash
# Specify custom configuration
python main.py input.pdf output.pptx --config custom_config.yaml

# Adjust DPI for image extraction
python main.py input.pdf output.pptx --dpi 300

# Enable debug logging
python main.py input.pdf output.pptx --log-level DEBUG
```

## Examples

### Example 1: Simple Conversion

```bash
python main.py tests/test_sample.pdf output/result.pptx
```

### Example 2: High-Quality Conversion

```bash
python main.py document.pdf output.pptx --dpi 600
```

### Example 3: Using Test Script

```bash
python test_convert.py
```

This will convert `tests/test_sample.pdf` to `output/test_output.pptx`.

## Configuration

Edit `config/config.yaml` to customize:

### PDF Parser Settings

```yaml
parser:
  dpi: 300                    # Image extraction DPI
  extract_images: true        # Extract images from PDF
  image_format: "PNG"         # Image format (PNG, JPEG)
  min_text_size: 6           # Minimum font size to extract
  max_text_size: 72          # Maximum font size to extract
```

### Layout Analyzer Settings

```yaml
analyzer:
  title_threshold: 20         # Font size threshold for titles
  min_paragraph_chars: 10     # Minimum characters for paragraph
  group_tolerance: 10         # Pixel tolerance for grouping
  detect_headers: true        # Detect page headers
  detect_footers: true        # Detect page footers
```

### Slide Dimensions

```yaml
rebuilder:
  slide_width: 10            # Slide width in inches
  slide_height: 7.5          # Slide height in inches (16:9)
  margin_left: 0.5           # Left margin
  margin_right: 0.5          # Right margin
  margin_top: 0.5            # Top margin
  margin_bottom: 0.5         # Bottom margin
```

### Font Mapping

```yaml
mapper:
  font_mapping:
    "SimHei": "Microsoft YaHei"
    "SimSun": "宋体"
    "Helvetica": "Arial"
    "Times": "Times New Roman"
  
  default_font: "Arial"
  default_font_size: 18
  title_font_size: 32
  preserve_colors: true
```

## Architecture

The converter uses a 5-layer pipeline:

1. **PDF Parser** - Extracts raw elements (text, images, shapes) with positions
2. **Layout Analyzer** - Detects semantic structure (titles, paragraphs, etc.)
3. **Element Rebuilder** - Transforms to slide model with normalized coordinates
4. **Style Mapper** - Maps PDF styles to PowerPoint formatting
5. **PPTX Generator** - Creates the final editable PowerPoint file

## Output

The converter produces:

- ✅ **Editable PPTX files** - Can be opened and edited in PowerPoint
- ✅ **Preserved text** - All text content with formatting
- ✅ **Extracted images** - Images placed at correct positions
- ✅ **Layout structure** - Attempts to maintain original layout
- ✅ **Font mapping** - Chinese and English fonts mapped appropriately

## Limitations

Current limitations:

- ⚠️ Complex tables may not be perfectly reconstructed
- ⚠️ Vector graphics are simplified to basic shapes
- ⚠️ Some advanced PDF features (forms, annotations) are not supported
- ⚠️ Font matching is best-effort based on available system fonts

## Tips for Best Results

1. **High-quality PDFs**: Work best with PDFs that have text layers (not scanned)
2. **Simple layouts**: PDFs with clear structure convert better
3. **Standard fonts**: Use common fonts for better mapping
4. **Adjust DPI**: Increase DPI (--dpi 600) for better image quality
5. **Custom config**: Create custom config for specific document types

## Troubleshooting

### Issue: Missing text

**Solution**: Check if PDF has text layer. Scanned PDFs may need OCR first.

### Issue: Wrong fonts

**Solution**: Update font mapping in `config/config.yaml`

### Issue: Layout issues

**Solution**: Adjust `group_tolerance` and margin settings in config

### Issue: Large file size

**Solution**: Enable image compression in config:

```yaml
generator:
  compress_images: true
  image_quality: 85
```

## Logging

Check `pdf2pptx.log` for detailed conversion logs.

Enable debug logging:

```bash
python main.py input.pdf output.pptx --log-level DEBUG
```

## Advanced Usage

### Programmatic Usage

```python
from main import convert_pdf_to_pptx, load_config, setup_logging

# Setup
setup_logging('INFO')
config = load_config('config/config.yaml')

# Convert
success = convert_pdf_to_pptx(
    'input.pdf',
    'output.pptx',
    config
)

if success:
    print("Conversion successful!")
```

### Custom Pipeline

```python
from src.parser.pdf_parser import PDFParser
from src.analyzer.layout_analyzer_v2 import LayoutAnalyzerV2
from src.rebuilder.coordinate_mapper import CoordinateMapper
from src.generator.pptx_generator import PPTXGenerator

# Load config
config = load_config()

# Step 1: Parse PDF
parser = PDFParser(config['parser'])
parser.open('input.pdf')
pages = parser.extract_all_pages()
parser.close()

# Step 2: Analyze layout
analyzer = LayoutAnalyzerV2(config['analyzer'])
analyzed_pages = [analyzer.analyze_page(page) for page in pages]

# Step 3: Build slide models
mapper = CoordinateMapper(config['rebuilder'])
slide_models = [mapper.create_slide_model(layout) for layout in analyzed_pages]

# Step 4: Generate PPTX
generator = PPTXGenerator(config['generator'])
generator.generate_from_models(slide_models)
generator.save('output.pptx')
```

## Performance

Typical conversion times:

- **Simple PDF (1-10 pages)**: < 1 second
- **Medium PDF (10-50 pages)**: 2-5 seconds
- **Large PDF (50-200 pages)**: 10-30 seconds
- **Very large PDF (200+ pages)**: 30+ seconds

Performance depends on:
- Number of pages
- Number of images
- Complexity of layout
- DPI setting for images

## Support

For issues or questions:
1. Check logs in `pdf2pptx.log`
2. Review this usage guide
3. Check README.md for architecture details
4. Adjust configuration for your specific needs
