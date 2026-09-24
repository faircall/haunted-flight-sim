"""Extract reusable native-pixel details from approved concepts. Does not change sources."""
from pathlib import Path
from PIL import Image, ImageFilter
import json
import statistics
ROOT = Path(__file__).resolve().parent
SPECS = {'grass': [(64, 31, 88, 57), (90, 34, 117, 62), (6, 61, 29, 87), (43, 61, 65, 84)], 'dirt': [(17, 45, 44, 70), (65, 44, 87, 68), (16, 63, 29, 76), (19, 31, 31, 42), (4, 106, 26, 124), (77, 100, 97, 122)], 'wood': [(41, 58, 50, 85), (112, 60, 122, 80), (73, 31, 80, 52)], 'tiles': [(36, 4, 60, 28), (68, 4, 92, 28), (5, 36, 28, 60), (100, 68, 124, 92)], 'wall': [(59, 29, 68, 65), (30, 63, 41, 78), (77, 88, 89, 111), (34, 93, 45, 119)]}

def build():
    out = ROOT / 'art' / 'surfaces'
    out.mkdir(parents=True, exist_ok=True)
    atlas = Image.new('RGBA', (256, 128))
    items = []
    for material, boxes in SPECS.items():
        directory = 'walls' if material == 'wall' else material
        source = sorted((ROOT / 'artdev' / 'concepts' / directory).glob('*.png'))[1 if material == 'tiles' else 0]
        with Image.open(source) as im:
            image = im.convert('RGB').resize((128, 128), Image.Resampling.NEAREST)
        for j, box in enumerate(boxes):
            piece = image.crop(box)
            w, h = piece.size
            if max(w, h) > 28:
                piece = piece.resize((round(w * 28 / max(w, h)), round(h * 28 / max(w, h))), Image.Resampling.NEAREST)
            w, h = piece.size
            rgba = piece.convert('RGBA')
            pixels = rgba.load()
            luminance = piece.convert('L')
            local = luminance.filter(ImageFilter.GaussianBlur(2))
            corners = [piece.getpixel(p) for p in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))]
            baseline = statistics.median((sum(c[:2]) / 2 for c in corners))
            for y in range(h):
                for x in range(w):
                    r, g, b = piece.getpixel((x, y))
                    edge = min(x, y, w - 1 - x, h - 1 - y)
                    ellipse = max(0.0, 1.0 - ((x - (w - 1) / 2) / (w / 2)) ** 2 - ((y - (h - 1) / 2) / (h / 2)) ** 2)
                    if material == 'grass':
                        alpha = 255 if ellipse > 0.02 and (r + g) / 2 > baseline + 3 else 0
                    elif material == 'tiles':
                        alpha = round(min(200, max(0, local.getpixel((x, y)) - luminance.getpixel((x, y)) - 2) * 24) * min(1.0, edge / 2))
                    else:
                        alpha = round(255 * min(1.0, ellipse * 5) * min(1.0, edge / 2))
                    pixels[x, y] = (r, g, b, alpha)
            if material == 'grass':
                seen = set()
                components = []
                for y in range(h):
                    for x in range(w):
                        if (x, y) in seen or not pixels[x, y][3]:
                            continue
                        todo = [(x, y)]
                        component = []
                        seen.add((x, y))
                        while todo:
                            a, b = todo.pop()
                            component.append((a, b))
                            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)):
                                p = (a + dx, b + dy)
                                if 0 <= p[0] < w and 0 <= p[1] < h and (p not in seen) and pixels[p][3]:
                                    seen.add(p)
                                    todo.append(p)
                        components.append(component)
                for component in components:
                    if len(component) < 5:
                        for p in component:
                            pixels[p] = (*pixels[p][:3], 0)
                rgba = rgba.crop(rgba.getbbox())
                w, h = rgba.size
            number = len(items)
            ax = number % 8 * 32
            ay = number // 8 * 32
            atlas.paste(rgba, (ax, ay))
            name = f'{material}_{j}'
            rgba.save(out / (name + '.png'))
            items.append(dict(name=name, material=material, rect=[ax, ay, w, h], root=[w / 2, h - 1], source=str(source.relative_to(ROOT)), crop=list(box)))
    atlas.save(out / 'details.png')
    (out / 'details.json').write_text(json.dumps(items, indent=2) + '\n')
    preview = Image.new('RGB', (1024, 512), (51, 56, 48))
    preview.paste(atlas.resize((1024, 512), Image.Resampling.NEAREST), (0, 0), atlas.resize((1024, 512), Image.Resampling.NEAREST))
    (ROOT / 'artifacts' / 'surfaces').mkdir(parents=True, exist_ok=True)
    preview.save(ROOT / 'artifacts' / 'surfaces' / 'details.png')
    print(f'Extracted {len(items)} detail sprites')
if __name__ == '__main__':
    build()
