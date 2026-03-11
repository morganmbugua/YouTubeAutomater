#!/usr/bin/env python3
"""
Step 6: Generate Thumbnail (Free)
Creates a clean gradient thumbnail with title text using Pillow.
No external APIs needed — completely free.
"""

import os, json
from pathlib import Path

SLOT       = os.environ.get("VIDEO_SLOT", "1")
OUTPUT_DIR = Path(f"output/slot_{SLOT}")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

topic_json = os.environ.get("TOPIC_DATA", "")
topic_data = json.loads(topic_json) if topic_json else json.loads((OUTPUT_DIR / "topic.json").read_text())

script_path = os.environ.get("SCRIPT_PATH", str(OUTPUT_DIR / "script.json"))
script_data = json.loads(Path(script_path).read_text()) if Path(script_path).exists() else {}

# Gradient palette — cycles through slots for visual variety
GRADIENTS = [
    ((26, 26, 46),  (233, 69, 96)),   # dark blue → red
    ((15, 52, 96),  (83, 52, 131)),   # navy → purple
    ((27, 38, 44),  (10, 61, 98)),    # dark teal → blue
    ((44, 62, 80),  (52, 152, 219)),  # charcoal → sky blue
    ((26, 26, 46),  (22, 33, 62)),    # dark blue gradient
    ((20, 74, 74),  (27, 108, 168)),  # teal → blue
]

def make_thumbnail(title: str, output_path: Path):
    slot_int = int(SLOT) - 1
    c1, c2   = GRADIENTS[slot_int % len(GRADIENTS)]

    try:
        from PIL import Image, ImageDraw, ImageFont
        img  = Image.new("RGB", (1280, 720))
        draw = ImageDraw.Draw(img)

        # Draw vertical gradient
        for y in range(720):
            t = y / 720
            r = int(c1[0] + t * (c2[0] - c1[0]))
            g = int(c1[1] + t * (c2[1] - c1[1]))
            b = int(c1[2] + t * (c2[2] - c1[2]))
            draw.line([(0, y), (1280, y)], fill=(r, g, b))

        # Dark overlay at bottom for text readability
        overlay = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
        draw_ol = ImageDraw.Draw(overlay)
        for y in range(300, 720):
            alpha = int(((y - 300) / 420) * 210)
            draw_ol.line([(0, y), (1280, y)], fill=(0, 0, 0, alpha))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(img)

        # Load font
        font_size = 64
        font      = None
        for fp in [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]:
            if Path(fp).exists():
                try:
                    font = ImageFont.truetype(fp, font_size)
                    break
                except Exception:
                    pass
        if font is None:
            font = ImageFont.load_default()

        # Word-wrap title to max 3 lines
        words = title.split()
        lines, line = [], []
        for word in words:
            test = " ".join(line + [word])
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] > 1180 and line:
                lines.append(" ".join(line))
                line = [word]
            else:
                line.append(word)
        if line:
            lines.append(" ".join(line))
        lines = lines[:3]

        total_h = len(lines) * (font_size + 12)
        start_y = 720 - total_h - 60

        for i, line_text in enumerate(lines):
            y    = start_y + i * (font_size + 12)
            bbox = draw.textbbox((0, 0), line_text, font=font)
            x    = (1280 - bbox[2]) // 2
            # Shadow
            draw.text((x + 3, y + 3), line_text, font=font, fill=(0, 0, 0, 180))
            # Main text
            draw.text((x, y), line_text, font=font, fill=(255, 255, 255))

        img.save(str(output_path), "JPEG", quality=95)
        print(f"   ✅ Thumbnail created with Pillow: {output_path.stat().st_size // 1024}KB")

    except ImportError:
        # Pillow not available — use ffmpeg
        print("   ⚠️ Pillow not available — using ffmpeg thumbnail")
        title_safe = title.replace("'", "\\'").replace(":", "\\:")[:40]
        r1, g1, b1 = c1; r2, g2, b2 = c2
        cmd = (
            f'ffmpeg -f lavfi '
            f'-i "color=c=#{r1:02x}{g1:02x}{b1:02x}:size=1280x720:rate=1" '
            f'-vf "drawtext=text=\'{title_safe}\':fontcolor=white:fontsize=48:'
            f'x=(w-text_w)/2:y=(h-text_h)/2:font=DejaVu-Sans-Bold" '
            f'-frames:v 1 "{output_path}" -y 2>/dev/null'
        )
        os.system(cmd)

def main():
    print(f"🖼️ Generating thumbnail for slot {SLOT}…")
    title          = script_data.get("title", topic_data.get("topic", "Video"))
    thumbnail_path = OUTPUT_DIR / "thumbnail.jpg"

    make_thumbnail(title, thumbnail_path)

    if not thumbnail_path.exists():
        raise RuntimeError("Thumbnail generation failed")

    gho = os.environ.get("GITHUB_OUTPUT", "/dev/null")
    with open(gho, "a") as f:
        f.write(f"thumbnail_path={thumbnail_path}\n")

    print(f"✅ Thumbnail ready: {thumbnail_path}")

if __name__ == "__main__":
    main()
