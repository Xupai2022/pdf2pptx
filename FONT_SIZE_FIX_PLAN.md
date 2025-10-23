# Font Size and Element Detail Fix Plan

## Problem Summary

The current conversion has inaccurate font sizes and element dimensions due to unit conversion issues between HTML pixels, PDF points, and PowerPoint points.

## Root Causes

### 1. Font Size Conversion Issue
- **HTML Reference**: Uses CSS pixels (e.g., `font-size: 48px`, `25px`, `20px`)
- **PDF Extraction**: PyMuPDF returns font sizes in PDF points (pt)
- **Current Scale**: `font_size_scale: 1.333` assumes PDF pt → screen px at 96 DPI
- **Problem**: This conversion is inconsistent with actual extracted values

### 2. Element Dimension Issues
- **HTML Specs**:
  - `top-bar` height: `10px`
  - `border-left` width: `4px`
- **Current Code**: Directly uses PDF-extracted stroke_width without proper px→pt conversion

### 3. Coordinate System Mismatch
- **HTML Canvas**: 1920×1080 pixels
- **PPTX Units**: Inches
- **Current Config**: `slide_width: 13.333"` assumes 144 DPI (1920px ÷ 144 = 13.333")
- **Standard**: Should use 72 DPI for PowerPoint (1920px ÷ 72 = 26.67")

## Industry Best Practices

### PowerPoint Coordinate System
- **Standard DPI**: 72 DPI (1 inch = 72 points = 72 pixels in PowerPoint)
- **Widescreen 16:9**: 10" × 5.625" (720×405 pt at 72 DPI)
- **Custom Size**: Can set to match HTML dimensions

### Font Size Mapping
According to PowerPoint standards:
- **Display**: 1 CSS px ≈ 0.75 pt (at 96 DPI web standard)
- **PDF to PPT**: 1 PDF pt = 1 PPT pt (both use PostScript points)
- **HTML to PPT**: Need to account for screen DPI difference

## Solution Strategy

### Phase 1: Fix Coordinate System
1. Use **72 DPI** as standard conversion factor
2. Calculate slide dimensions: 1920px ÷ 72 = 26.67", 1080px ÷ 72 = 15"
3. Update config with correct `slide_width` and `slide_height`

### Phase 2: Fix Font Size Conversion
1. **Remove font_size_scale** or set to 1.0 (PDF pt = PPT pt)
2. Add **PDF-to-HTML font size analysis** to determine actual scale
3. Use direct mapping: If HTML says 48px and PDF extracts 48pt, use 48pt in PPT
4. If mismatch exists, calculate correction factor from test data

### Phase 3: Fix Element Dimensions
1. **Border widths**: Convert HTML px directly to PPT pt (1:1 at 72 DPI)
   - HTML `border-left: 4px` → PPT `4pt`
   - HTML `height: 10px` → PPT `10pt`
2. **Shape stroke widths**: Use pixel values from HTML, not PDF extractions
3. Ensure `stroke_width` in coordinate_mapper preserves original px values

### Phase 4: Precise Detail Extraction
1. Create analyzer to detect:
   - Top bar: height = 10px
   - Card borders: width = 4px (left border)
   - Font sizes: 48px (h1), 36px (h2), 28px (h3), 25px (p), 20px (small), 14px (page number)
2. Map these precisely to PPT equivalents

## Implementation Steps

1. **Update config.yaml**:
   - `slide_width: 26.67` (1920px ÷ 72)
   - `slide_height: 15` (1080px ÷ 72)
   - `font_size_scale: 1.0` (start with no scaling)

2. **Update style_mapper.py**:
   - Remove scaling or use accurate factor
   - Add font size mapping table based on HTML reference

3. **Update coordinate_mapper.py**:
   - Use 72 DPI for all px→inch conversions
   - Preserve stroke_width in points (1px = 1pt)

4. **Create test analysis script**:
   - Compare PDF extracted values vs HTML reference
   - Calculate actual correction factors
   - Generate mapping table

## Validation Criteria

- [ ] Top bar height = 0.139" (10pt ÷ 72)
- [ ] Border width = 0.056" (4pt ÷ 72)
- [ ] H1 font size = 48pt
- [ ] H2 font size = 36pt
- [ ] H3 font size = 28pt
- [ ] Body text = 25pt
- [ ] Small text = 20pt
- [ ] Page number = 14pt
- [ ] Slide dimensions = 26.67" × 15"

## References

- HTML Reference: `tests/slide11_reference.html`
- PowerPoint Standards: 72 DPI, PostScript points
- CSS Pixels: 96 DPI web standard
