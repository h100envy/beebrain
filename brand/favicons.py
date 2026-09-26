"""
favicon set from the avatar: 16, 32, 180 (apple touch), 192, 512 px and a multi size favicon.ico.
needs pillow. run brand/hexbrain.py first.

idea credited to the nerve protocol, github.com/h100envy/nerve
"""
import os

from PIL import Image

from common import BRAND_OUT


def square_crop(im):
    # the brain sits a little low in the avatar, trim the empty sky so small sizes read
    w, h = im.size
    box = (int(w * 0.10), int(h * 0.12), int(w * 0.90), int(h * 0.92))
    return im.crop(box)


def main():
    src = Image.open(os.path.join(BRAND_OUT, "avatar.png")).convert("RGB")
    tight = square_crop(src)
    sizes = {"favicon-16.png": (16, tight), "favicon-32.png": (32, tight), "apple-touch-icon.png": (180, src),
             "icon-192.png": (192, src), "icon-512.png": (512, src)}
    for name, (px, im) in sizes.items():
        im.resize((px, px), Image.LANCZOS).save(os.path.join(BRAND_OUT, name), optimize=True)
        print("wrote web/assets/brand/" + name)
    tight.resize((64, 64), Image.LANCZOS).save(os.path.join(BRAND_OUT, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48)])
    print("wrote web/assets/brand/favicon.ico")


if __name__ == "__main__":
    main()
