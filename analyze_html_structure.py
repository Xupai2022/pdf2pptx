#!/usr/bin/env python3
"""
Analyze HTML structure in detail to understand exact layout requirements
"""

from bs4 import BeautifulSoup
from pathlib import Path

def analyze_html():
    """Analyze HTML structure."""
    
    html_path = "tests/slide11_reference.html"
    
    if not Path(html_path).exists():
        print(f"❌ HTML file not found: {html_path}")
        return
    
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
    
    print("="*80)
    print("HTML STRUCTURE ANALYSIS")
    print("="*80)
    
    # Overall dimensions
    print("\n1. PAGE DIMENSIONS:")
    print("   - Width: 1920px")
    print("   - Height: 1080px")
    print("   - Aspect ratio: 16:9")
    
    # Top bar
    print("\n2. TOP BAR (.top-bar):")
    print("   - Height: 10px")
    print("   - Width: 100% (1920px)")
    print("   - Background: rgb(10, 66, 117) / #0a4275")
    
    # Content section
    print("\n3. CONTENT SECTION (.content-section):")
    print("   - Padding: 40px 80px 60px 80px")
    print("   - Effective area: (80, 50) to (1840, 1020)")
    print("   - Effective size: 1760px × 970px")
    
    # Title section
    print("\n4. TITLE SECTION:")
    print("   - H1 (main title):")
    print("     * Text: '风险资产深度剖析'")
    print("     * Font-size: 48px")
    print("     * Color: rgb(10, 66, 117)")
    print("     * Position: ~(80, 50)")
    print("   - H2 (subtitle):")
    print("     * Text: '典型高风险资产案例展示'")
    print("     * Font-size: 36px")
    print("     * Color: #666 (gray)")
    print("   - Underline:")
    print("     * Width: 80px (20px in css, but w-20 = 5rem = 80px)")
    print("     * Height: 4px (h-1 = 0.25rem = 4px)")
    print("     * Color: rgb(10, 66, 117)")
    
    # Stat cards
    print("\n5. STAT CARDS (.stat-card, grid-cols-3):")
    print("   - Container: grid with 3 columns, gap-6 (24px)")
    print("   - Each card:")
    print("     * Width: ~(1760-48)/3 = 571px per card")
    print("     * Background: rgba(10, 66, 117, 0.08) ← SEMI-TRANSPARENT")
    print("     * Border-radius: 8px")
    print("     * Border-left: 4px solid rgb(10, 66, 117)")
    print("     * Padding: 15px 20px")
    print("\n   Card 1 - 高风险资产总数:")
    print("     * Title: '高风险资产总数' (text-2xl = 24px)")
    print("     * Number: '8个' (text-4xl = 36px, color: red-600 #dc2626)")
    print("     * Subtitle: '需立即处理' (text-lg = 18px, gray-600)")
    print("\n   Card 2 - 风险分布:")
    print("     * Title: '风险分布' (24px)")
    print("     * Labels with colored backgrounds:")
    print("       - '高危4': bg rgba(220,38,38,0.1), color #dc2626")
    print("       - '中危12': bg rgba(245,158,11,0.1), color #f59e0b")
    print("       - '低危19': bg rgba(59,130,246,0.1), color #3b82f6")
    print("\n   Card 3 - 云存储风险:")
    print("     * Similar to Card 1")
    
    # Detail sections
    print("\n6. DETAIL SECTIONS (.data-card, grid-cols-2):")
    print("   - Container: 2 columns, gap-6 (24px)")
    print("   - Each card:")
    print("     * Width: ~(1760-24)/2 = 868px")
    print("     * Background: rgba(10, 66, 117, 0.03) ← VERY LIGHT")
    print("     * Border-left: 4px solid rgb(10, 66, 117)")
    print("     * Border-radius: 8px")
    print("     * Padding: 15px 20px")
    print("\n   Left: '关键风险资产' (3 items with icons)")
    print("   Right: '最新发现威胁（近一周）' (3 items with icons)")
    
    # Impact section
    print("\n7. IMPACT ANALYSIS (.data-card, grid-cols-4):")
    print("   - Container: 4 columns")
    print("   - Background: rgba(10, 66, 117, 0.03)")
    print("   - Border-left: 4px solid rgb(10, 66, 117)")
    
    # Risk level badges
    print("\n8. RISK LEVEL BADGES (.risk-level):")
    print("   - .risk-high:")
    print("     * Background: rgba(220, 38, 38, 0.1)")
    print("     * Color: #dc2626")
    print("     * Font-size: 20px")
    print("     * Padding: 2px 8px")
    print("     * Border-radius: 4px")
    print("\n   - .risk-medium:")
    print("     * Background: rgba(245, 158, 11, 0.1)")
    print("     * Color: #f59e0b")
    print("\n   - .risk-low:")
    print("     * Background: rgba(59, 130, 246, 0.1)")
    print("     * Color: #3b82f6")
    
    # Icons
    print("\n9. ICONS (FontAwesome):")
    print("   - Size: default (inherits from parent font-size)")
    print("   - Color: rgb(10, 66, 117) for bullet icons")
    print("   - Color: #dc2626 for risk icons")
    
    print("\n" + "="*80)
    print("KEY FINDINGS:")
    print("="*80)
    print("❗ PDF page is 1440×811 but should map to 1920×1080")
    print("❗ Semi-transparent backgrounds need to be rendered")
    print("❗ 4px borders are critical visual elements")
    print("❗ Text should not wrap - containers are wide enough")
    print("❗ Grid layouts with specific gaps (24px)")
    print("="*80)


if __name__ == '__main__':
    analyze_html()
