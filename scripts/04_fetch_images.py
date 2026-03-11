#!/usr/bin/env python3
"""
Step 4: Fetch Topic Images from Pexels
Downloads high-quality stock photos relevant to the video topic.
These are used instead of an AI avatar — results in a more professional
documentary/explainer style that works better for most topics.

Falls back to colored gradient frames if Pexels is unavailable.
"""

import os, json, urllib.request, urllib.parse, time
from pathlib import Path

SLOT       = os.environ.get("VIDEO_SLOT", "1")
OUTPUT_DIR = Path(f"output/slot_{SLOT}")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")
IMAGES_DIR     = OUTPUT_DIR / "images"
IMAGES_DIR.mkdir(exist_ok=True)

# Load topic data
topic_json = os.environ.get("TOPIC_DATA", "")
if topic_json:
    topic_data = json.loads(topic_json)
else:
    topic_data = json.loads((OUTPUT_DIR / "topic.json").read_text())

# We want ~20 images total spread across the video
TARGET_IMAGES = 20

# ── Pexels image fetcher ──────────────────────────────────────────────────────

def fetch_pexels_images(query: str, per_page: int = 5) -> list[dict]:
    """Fetch images from Pexels API for a given search query."""
    if not PEXELS_API_KEY:
        return []
    try:
        params = urllib.parse.urlencode({
            "query": query,
            "per_page": per_page,
            "orientation": "landscape",
            "size": "large"
        })
        url = f"https://api.pexels.com/v1/search?{params}"
        req = urllib.request.Request(url, headers={"Authorization": PEXELS_API_KEY})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        photos = data.get("photos", [])
        print(f"   Pexels '{query}': {len(photos)} results")
        return photos
    except Exception as e:
        print(f"   ⚠️ Pexels query '{query}' failed: {e}")
        return []

def download_image(photo: dict, index: int) -> str | None:
    """Download a Pexels photo and return local path."""
    try:
        url = photo["src"]["large2x"]  # 1920px wide
        ext = url.split("?")[0].split(".")[-1].lower()
        if ext not in ["jpg", "jpeg", "png"]:
            ext = "jpg"
        path = IMAGES_DIR / f"img_{index:03d}.{ext}"
        urllib.request.urlretrieve(url, str(path))
        return str(path)
    except Exception as e:
        print(f"   ⚠️ Download failed for photo {photo.get('id')}: {e}")
        return None

def fetch_all_images(topic_data: dict) -> list[str]:
    """Fetch images for all image_queries from topic data."""
    image_queries = topic_data.get("image_queries", [topic_data.get("search_query", topic_data["topic"])])
    all_photos: list[dict] = []
    seen_ids: set = set()

    for query in image_queries:
        photos = fetch_pexels_images(query, per_page=5)
        for p in photos:
            if p["id"] not in seen_ids:
                seen_ids.add(p["id"])
                all_photos.append(p)
        if len(all_photos) >= TARGET_IMAGES:
            break
        time.sleep(0.3)  # Be polite to the API

    # Download what we have
    paths = []
    for i, photo in enumerate(all_photos[:TARGET_IMAGES]):
        path = download_image(photo, i)
        if path:
            paths.append(path)

    return paths

# ── Gradient fallback ─────────────────────────────────────────────────────────

def generate_gradient_frames(count: int) -> list[str]:
    """
    Generate colored gradient images using ffmpeg.
    Used when Pexels is unavailable (no API key or all queries fail).
    """
    print("   Generating gradient fallback frames…")
    # A palette of nice dark gradient colors
    colors = [
        ("0x1a1a2e", "0x16213e"), ("0x0f3460", "0x533483"),
        ("0x1b262c", "0x0a3d62"), ("0x2c3e50", "0x3498db"),
        ("0x1a1a2e", "0xe94560"), ("0x134074", "0x1b6ca8"),
    ]
    paths = []
    for i in range(count):
        c1, c2 = colors[i % len(colors)]
        path = IMAGES_DIR / f"img_{i:03d}.png"
        cmd = (
            f'ffmpeg -f lavfi '
            f'-i "gradients=s=1920x1080:c0={c1}:c1={c2}:nb_colors=2:x0=0:y0=0:x1=1920:y1=1080" '
            f'-frames:v 1 "{path}" -y 2>/dev/null'
        )
        os.system(cmd)
        if path.exists():
            paths.append(str(path))
    print(f"   Generated {len(paths)} gradient frames")
    return paths

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"🖼️ Fetching images for slot {SLOT}: {topic_data['topic']}")

    if PEXELS_API_KEY:
        image_paths = fetch_all_images(topic_data)
        print(f"   Downloaded {len(image_paths)} images from Pexels")
    else:
        print("   No PEXELS_API_KEY — using gradient fallback")
        image_paths = []

    # If we got fewer than 10 images, pad with gradients
    if len(image_paths) < 10:
        needed = max(TARGET_IMAGES - len(image_paths), 10 - len(image_paths))
        fallbacks = generate_gradient_frames(needed)
        image_paths.extend(fallbacks)

    if not image_paths:
        raise RuntimeError("No images available — cannot build video")

    # Save image list
    images_meta = {"paths": image_paths, "count": len(image_paths)}
    images_meta_path = OUTPUT_DIR / "images_meta.json"
    images_meta_path.write_text(json.dumps(images_meta, indent=2))

    print(f"✅ {len(image_paths)} images ready")

    gho = os.environ.get("GITHUB_OUTPUT", "/dev/null")
    with open(gho, "a") as f:
        f.write(f"images_meta_path={images_meta_path}\n")
        f.write(f"image_count={len(image_paths)}\n")

if __name__ == "__main__":
    main()
