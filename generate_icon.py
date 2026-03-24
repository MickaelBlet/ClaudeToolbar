"""Generate app icon (ICO) for the exe."""
from PIL import Image, ImageDraw, ImageFont

sizes = [16, 32, 48, 64, 128, 256]
images = []

for size in sizes:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background: rounded rectangle with dark theme
    radius = max(2, size // 8)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill="#1a1a2e")

    # Draw "C" letter in Claude's orange/amber color
    try:
        font_size = int(size * 0.7)
        font = ImageFont.truetype("arialbd.ttf", font_size)
    except OSError:
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except OSError:
            font = ImageFont.load_default()

    text = "C"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        ((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1]),
        text,
        fill="#d4a574",
        font=font,
    )
    images.append(img)

# Save as ICO - largest image first, append smaller ones
images[-1].save(
    "assets/app_icon.ico",
    format="ICO",
    append_images=images[:-1],
)

# Verify
ico = Image.open("assets/app_icon.ico")
print(f"Generated assets/app_icon.ico ({ico.info.get('sizes', 'unknown sizes')})")
print(f"File size: {__import__('os').path.getsize('assets/app_icon.ico')} bytes")
