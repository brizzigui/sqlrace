import hashlib

def generate_identicon_svg(identifier: str, size: int = 120) -> str:
    """
    Generates a GitHub-style 5x5 symmetric SVG identicon string based on identifier.
    """
    clean_id = (identifier or "team").strip().lower()
    hash_bytes = hashlib.sha256(clean_id.encode('utf-8')).digest()
    
    # Calculate hue from first two bytes (0 to 359)
    hue = (hash_bytes[0] << 8 | hash_bytes[1]) % 360
    fg_color = f"hsl({hue}, 70%, 55%)"
    bg_color = f"hsl({hue}, 30%, 12%)"
    border_color = f"hsl({hue}, 60%, 25%)"
    
    # Generate 5x5 grid from hash bytes
    # 5 rows x 3 cols = 15 bits
    grid = []
    bit_index = 0
    for r in range(5):
        row = []
        for c in range(3):
            byte_val = hash_bytes[2 + bit_index]
            is_filled = (byte_val % 2 == 0)
            row.append(is_filled)
            bit_index += 1
        # Mirror col 1 to col 3, col 0 to col 4
        row.append(row[1])
        row.append(row[0])
        grid.append(row)
        
    # Ensure at least 4 filled cells so avatar is not empty
    filled_count = sum(sum(1 for cell in row if cell) for row in grid)
    if filled_count < 4:
        for r in range(5):
            grid[r][2] = True
            
    # Build SVG XML string
    rects = []
    # Grid offset: 10px margin, cell size 16px -> 5 * 16 = 80px total grid inside 100x100 canvas
    for r in range(5):
        for c in range(5):
            if grid[r][c]:
                x = 10 + c * 16
                y = 10 + r * 16
                rects.append(f'<rect x="{x}" y="{y}" width="16" height="16" rx="3" fill="{fg_color}" />')
                
    rects_xml = "\n    ".join(rects)
    
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="{size}" height="{size}">
    <rect width="100" height="100" rx="20" fill="{bg_color}" stroke="{border_color}" stroke-width="2"/>
    {rects_xml}
</svg>"""
    return svg
