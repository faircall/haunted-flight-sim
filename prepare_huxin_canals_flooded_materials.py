"""Pack the Void Canals' original material sheet into padded Dreamcast tiles.

Run with the project's Python environment. The checked-in source is the original
imagegen output; rebuilding requires only Pillow and NumPy, not an image API.
Each material occupies a 256px atlas cell, with its 128px image centered at
(64, 64). The 64px repeated edge padding matches the existing Mesh UV contract.
"""
from pathlib import Path
import hashlib
import json

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'art' / 'temple' / 'huxin_canals_flooded'
TILES = ('wood', 'roof', 'stone', 'paint', 'earth', 'moss', 'leaf',
         'leaflight', 'cap', 'bronze', 'paper', 'cloth', 'plaster',
         'wetstone', 'bark', 'water')
SIZE = 128


def noise(seed, scale=12):
    rng = np.random.default_rng(seed)
    field = Image.fromarray(rng.integers(0, 256, (scale, scale), dtype=np.uint8))
    return np.asarray(field.resize((SIZE, SIZE), Image.Resampling.BICUBIC),
                      dtype=np.float32) / 255


def image(rgb):
    return Image.fromarray(np.uint8(np.clip(rgb, 0, 255)))


def tone(tile, multiply=(1., 1., 1.), lift=(0., 0., 0.)):
    return image(np.asarray(tile, dtype=np.float32) * multiply + lift)


def surface(base, seed, amplitude=24):
    variation = (noise(seed, 7) - .5) * amplitude
    variation += (noise(seed + 1, 39) - .5) * amplitude * .50
    variation += (noise(seed + 2, 128) - .5) * amplitude * .22
    return np.array(base)[None, None, :] + variation[:, :, None]


def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    source_path = OUT / 'canal_materials_source.png'
    source = Image.open(source_path).convert('RGB')
    width, height = source.size
    originals = {}
    for quadrant, name in enumerate(('wood', 'roof', 'stone', 'plaster')):
        x, y = quadrant % 2, quadrant // 2
        crop = source.crop((x * width // 2, y * height // 2,
                            (x + 1) * width // 2, (y + 1) * height // 2))
        originals[name] = crop.resize((SIZE, SIZE), Image.Resampling.LANCZOS)

    # The primary four retain the original physical detail. Their low saturation
    # is deliberate: the environment lighting and water supply the cold hue.
    tiles = dict(originals)
    tiles['paint'] = tone(originals['wood'], (.70, .77, .78), (4, 5, 5))
    tiles['wetstone'] = tone(originals['stone'], (.64, .69, .66), (0, 1, 0))
    tiles['bark'] = tone(originals['wood'], (.84, .89, .79), (3, 3, 1))
    tiles['cap'] = tone(originals['roof'], (.79, .81, .80), (2, 2, 2))

    earth = surface((61, 61, 51), 781, 29)
    tiles['earth'] = image(earth)
    moss = surface((49, 59, 42), 116, 37)
    colonies = np.maximum(0, noise(91, 29) - .44)
    moss += colonies[:, :, None] * np.array((25, 34, 12))
    tiles['moss'] = image(moss)

    # Auxiliary tiles support the shared 16-material contract, including dry
    # reeds, decrepit domestic props and restrained residual foliage.
    leaf = surface((37, 47, 36), 7811, 29)
    tiles['leaf'] = image(leaf)
    tiles['leaflight'] = image(leaf + np.array((17, 19, 12)))
    oxide = noise(823, 18)
    bronze = surface((70, 72, 60), 94, 21)
    bronze += np.maximum(0, oxide - .55)[:, :, None] * np.array((-50, 14, 1))
    tiles['bronze'] = image(bronze)

    paper = surface((170, 166, 143), 600, 27)
    fy, fx = np.mgrid[:SIZE, :SIZE]
    fibres = np.sin(fx * 2.1 + noise(703, 32) * 2) * 1.8
    paper += fibres[:, :, None]
    tiles['paper'] = image(paper)
    cloth = surface((91, 91, 82), 719, 20)
    weave = np.where((fx + fy) % 2 == 0, 2., -2.)
    cloth += weave[:, :, None]
    tiles['cloth'] = image(cloth)
    water = surface((32, 45, 45), 811, 9)
    water += (np.sin(fy * .22 + noise(721, 5) * 3) * 1.8)[:, :, None]
    tiles['water'] = image(water)

    atlas = Image.new('RGB', (1024, 1024))
    preview = Image.new('RGB', (1024, 1152), (24, 28, 28))
    labels = ImageDraw.Draw(preview)
    font = ImageFont.truetype('C:/Windows/Fonts/consola.ttf', 18)
    stats = {}
    for index, name in enumerate(TILES):
        tile = tiles[name]
        pixels = np.asarray(tile)
        padded = Image.fromarray(np.pad(pixels, ((64, 64), (64, 64), (0, 0)),
                                       mode='edge'))
        atlas.paste(padded, (index % 4 * 256, index // 4 * 256))
        x, y = index % 4 * 256, index // 4 * 288
        preview.paste(tile.resize((256, 256), Image.Resampling.NEAREST), (x, y))
        labels.text((x + 9, y + 263), f'{index:02d} {name}', font=font,
                    fill=(190, 197, 188))
        stats[name] = dict(index=index,
                           average_rgb=[round(float(v), 2) for v in pixels.mean((0, 1))],
                           center_pixels=128,
                           padding=64)

    atlas_path = OUT / 'canal_materials.png'
    atlas.save(atlas_path, optimize=True)
    preview.save(OUT / 'canal_materials_preview.png', optimize=True)
    manifest = dict(source='canal_materials_source.png',
                    source_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(),
                    source_tool='built-in image_gen',
                    prompt='canal_materials_prompt.txt',
                    atlas=atlas_path.name,
                    atlas_sha256=hashlib.sha256(atlas_path.read_bytes()).hexdigest(),
                    dimensions=[1024, 1024], material_tiles=stats,
                    generated_quadrants=['wood', 'roof', 'stone', 'plaster'],
                    notes='Original generated imagery; no book photographs are copied into the game. '
                          'Auxiliary materials are derived tones and deterministic low-resolution synthesis.')
    (OUT / 'canal_materials_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n',
                                                       encoding='utf-8')
    print(f'Packed {len(TILES)} materials: {atlas_path}')


if __name__ == '__main__':
    prepare()
