"""Photo -> 300x340 1-bit Floyd-Steinberg dot maps (dark + light mode).

Outputs data/dots_dark.npy, data/dots_light.npy (bool, shape (340, 300), True = draw a dot)
and data/preview_*.png for eyeballing.
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from scipy import ndimage as ndi

HERE = Path(__file__).parent
PHOTO = HERE.parent / "assets" / "Professtional_Photo.png"
W, H = 300, 340
# head + shoulders crop (x0, y0, x1, y1) in source pixels; ratio must equal W:H
CROP = (28, 20, 868, 972)
CONTRAST = 1.3
DARK_GAMMA = 0.7   # <1 lifts shadows so dark hair still leaves some dots on the dark panel
DARK_RANGE = (0.16, 0.80)  # floor keeps hair textured, ceiling stops the white shirt going solid
LIGHT_BG_LIFT = 0.45       # blend backdrop toward white so it reads as texture, not noise
BG_DIST = 34       # colour distance from backdrop that counts as subject


def load_crop():
    im = Image.open(PHOTO).convert("RGB")
    return im.crop(CROP).resize((W, H), Image.LANCZOS)


def subject_mask(rgb):
    a = np.asarray(rgb).astype(float)
    # backdrop colour = median of the top strip corners (flat grey wall)
    patches = np.concatenate([a[:25, :25].reshape(-1, 3), a[:25, -25:].reshape(-1, 3)])
    bg = np.median(patches, axis=0)
    dist = np.sqrt(((a - bg) ** 2).sum(-1))
    m = dist > BG_DIST
    m = ndi.binary_closing(m, structure=np.ones((3, 3)), iterations=3)
    m = ndi.binary_fill_holes(m)
    lab, n = ndi.label(m)
    if n > 1:
        sizes = ndi.sum(m, lab, range(1, n + 1))
        m = lab == (1 + int(np.argmax(sizes)))
    m = ndi.binary_opening(m, structure=np.ones((3, 3)), iterations=1)
    return m


def tone(rgb, gamma=1.0):
    g = ImageOps.grayscale(rgb)
    g = ImageOps.autocontrast(g, cutoff=1)
    g = ImageEnhance.Contrast(g).enhance(CONTRAST)
    g = g.filter(ImageFilter.UnsharpMask(radius=3, percent=140))
    a = np.asarray(g).astype(float) / 255.0
    if gamma != 1.0:
        a = a ** gamma
    return a


def floyd_steinberg(a, mask=None):
    """Serpentine FS. Returns bool array, True where output is white (bright).
    With a mask, pixels outside are forced to 0 and never diffuse error."""
    a = a.copy()
    h, w = a.shape
    out = np.zeros((h, w), bool)
    for y in range(h):
        ltr = y % 2 == 0
        xs = range(w) if ltr else range(w - 1, -1, -1)
        d = 1 if ltr else -1
        for x in xs:
            if mask is not None and not mask[y, x]:
                continue
            old = a[y, x]
            new = 1.0 if old >= 0.5 else 0.0
            out[y, x] = new == 1.0
            err = old - new

            def push(xx, yy, f):
                if 0 <= xx < w and 0 <= yy < h and (mask is None or mask[yy, xx]):
                    a[yy, xx] += err * f

            push(x + d, y, 7 / 16)
            push(x - d, y + 1, 3 / 16)
            push(x, y + 1, 5 / 16)
            push(x + d, y + 1, 1 / 16)
    return out


def main():
    (HERE / "data").mkdir(exist_ok=True)
    rgb = load_crop()
    mask = subject_mask(rgb)
    np.save(HERE / "data" / "mask.npy", mask)

    td = DARK_RANGE[0] + (DARK_RANGE[1] - DARK_RANGE[0]) * tone(rgb, DARK_GAMMA)
    dark = floyd_steinberg(td, mask)                            # dots = lit subject
    dark &= mask                                                # hard-clear edge bleed
    tl = tone(rgb)
    tl = np.where(mask, tl, tl * (1 - LIGHT_BG_LIFT) + LIGHT_BG_LIFT)
    light = ~floyd_steinberg(tl, None)                          # dots = dark parts, keep backdrop
    np.save(HERE / "data" / "dots_dark.npy", dark)
    np.save(HERE / "data" / "dots_light.npy", light)

    s = 3
    for name, d, bg, fg in (("dark", dark, (10, 16, 31), (167, 139, 250)),
                            ("light", light, (245, 247, 252), (124, 58, 237))):
        img = np.zeros((H, W, 3), np.uint8)
        img[:] = bg
        img[d] = fg
        Image.fromarray(img).resize((W * s, H * s), Image.NEAREST).save(HERE / "data" / f"preview_{name}.png")
    Image.fromarray((mask * 255).astype(np.uint8)).resize((W * 2, H * 2)).save(HERE / "data" / "preview_mask.png")
    print("dots dark/light:", int(dark.sum()), int(light.sum()), "mask px:", int(mask.sum()))


if __name__ == "__main__":
    main()
