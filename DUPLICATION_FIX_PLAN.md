# Duplication Fix Plan

## Problem Analysis

### Root Cause
When `_check_image_quality()` returns `'rerender'`, the code re-renders the **entire PDF region** using:
```python
region_pix = page.get_pixmap(matrix=matrix, clip=rect, alpha=False)
```

This captures EVERYTHING in that rectangle:
- Vector shapes (lines, circles, etc.)
- Text elements  
- The original embedded image

Since text and shapes are extracted separately, this causes duplication.

### Specific Issues

**Page 4 - Triangle Region:**
- Original PDF has 3 vector lines forming a triangle
- One or more embedded images in that region get marked for rerender
- Rerendering captures the vector lines → PNG image contains lines
- Vector lines are also extracted separately → duplication
- Result: Triangle appears twice (blurry overlap)

**Page 6 - Large Image:**
- Large embedded PNG (341x418px) gets marked for rerender  
- Rerendering captures the region including "30.46分" text above/within image
- Text "30.46分" is also extracted separately as text element
- Result: Text appears twice (offset shadow)

## Solution Strategy

### Option 1: Don't Rerender - Use Original Image (RECOMMENDED)
**Rationale**: The original embedded images are actually fine. The "large PNG detection" logic is too aggressive.

**Implementation**:
- Remove or significantly restrict the "large PNG rerender" logic (Check 3 in `_check_image_quality`)
- Only rerender truly corrupted images (all black/all white)
- Keep the low-quality icon detection and enhancement
- Keep the skip logic for low-quality rasterized vectors

**Changes**:
1. In `_check_image_quality()`, remove or restrict Check 3 (lines 1022-1040)
2. Only apply rerender for truly corrupted images

### Option 2: Detect Overlaps Before Rerendering (COMPLEX)
**Rationale**: Check if the image region overlaps with vector shapes or text, and skip rerendering if so.

**Implementation**:
- Before rerendering, check if image bounds overlap with any extracted shapes
- This requires restructuring the extraction order
- More complex and error-prone

### Option 3: Extract Only the Embedded Image Data (COMPLEX)
**Rationale**: Re-render only the embedded image itself, not the entire region.

**Implementation**:
- Complex because PyMuPDF doesn't easily allow "isolating" just the image
- Would require masking or more sophisticated rendering

## Recommended Fix: Option 1

Remove the aggressive "large PNG rerender" logic. The images are actually fine quality - the problem is that rerendering captures too much.

### Code Changes Required

#### File: `src/parser/pdf_parser.py`

**Change 1**: Remove or restrict Check 3 in `_check_image_quality()` (lines 1022-1040)

```python
# BEFORE (lines 1022-1040):
# Check 3: Large PNG images with jagged edges or low quality
is_large = (width > 200 or height > 200)

if is_large and pil_image.mode == 'RGB':
    logger.info(
        f"Detected large PNG image: {width}x{height}px - will re-render at high resolution for better quality"
    )
    return 'rerender'

# AFTER:
# Check 3: REMOVED - Large images don't need rerendering
# The original embedded images are already good quality.
# Rerendering captures extra content (text, shapes) causing duplication.
# Only rerender truly corrupted images (handled in Check 1).
```

This is the cleanest fix that solves both issues:
- Page 4: Embedded images in triangle region won't be rerendered, so vector lines won't be captured
- Page 6: Large embedded PNG won't be rerendered, so text won't be captured

### Testing Strategy

1. **Verify Page 4**: No PNG overlays in triangle region, only vector lines visible
2. **Verify Page 6**: Large image exists, but text "30.46分" appears only once  
3. **Verify no regression**: Run regression tests on other PDFs
4. **Visual inspection**: Compare output PPTX with original PDF

## Alternative: More Selective Rerendering

If we still want to improve large image quality, we could:

1. Only rerender if image has VERY low resolution (< 100px)
2. Only rerender if image is extremely pixelated (check pixel variance)
3. Add overlap detection to skip rerendering when shapes/text overlap

But Option 1 is simpler and safer.
