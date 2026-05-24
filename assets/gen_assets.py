"""Generate all icon assets from the user-provided logos."""
from PIL import Image
from pathlib import Path

HERE = Path(__file__).resolve().parent
src = Image.open(HERE / "compressly-logo.png").convert("RGBA")

# icon.png — 512x512 master for HiDPI
master = src.resize((512, 512), Image.Resampling.LANCZOS)
master.save(HERE / "icon.png", format="PNG", optimize=True)

# icon.ico — all sizes rendered individually for maximum sharpness
sizes_px = [256, 128, 64, 48, 32, 16]
frames = [src.resize((s, s), Image.Resampling.LANCZOS) for s in sizes_px]
frames[0].save(
    HERE / "icon.ico",
    format="ICO",
    sizes=[(s, s) for s in sizes_px],
    append_images=frames[1:],
)

# logo_small.png — 32x32 for the collapsed sidebar corner
logo_small = src.resize((32, 32), Image.Resampling.LANCZOS)
logo_small.save(HERE / "logo_small.png", format="PNG")

# logo_text_dark.png  — dark mode text logo scaled to 22px tall
# logo_text_light.png — light mode text logo scaled to 22px tall
TARGET_H = 22
for variant in ("darkmode", "lightmode"):
    text_src = Image.open(HERE / f"compressly-{variant}.png").convert("RGBA")
    ratio = TARGET_H / text_src.height
    new_w = int(text_src.width * ratio)
    scaled = text_src.resize((new_w, TARGET_H), Image.Resampling.LANCZOS)
    out_name = f"logo_text_{variant.replace('mode','')}.png"
    scaled.save(HERE / out_name, format="PNG")
    print(f"{out_name}  {new_w}x{TARGET_H}")

ico_size = (HERE / "icon.ico").stat().st_size // 1024
png_size = (HERE / "icon.png").stat().st_size // 1024
print(f"icon.png       {png_size} KB  (512x512)")
print(f"icon.ico       {ico_size} KB  (6 sizes: 16-256)")
print(f"logo_small.png 32x32")
print("Done.")
