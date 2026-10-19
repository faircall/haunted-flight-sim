"""Small world-space building field for the canal fog; no asset rebuilding.

R is coverage: one inside an authored house footprint, falling smoothly to zero
four metres outside it. G is the associated roof height divided by 16 metres.
B is unused and A is opaque. Row zero represents the minimum world Z, not north
on a screen; sample UV=(worldXZ-bounds.xy)/(bounds.zw-bounds.xy).
"""
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / 'art' / 'temple' / 'huxin_canals' / 'canals_manifest.json'
COVERAGE_BOUNDS = (-96., -96., 96., 96.)  # min X, min Z, max X, max Z
COVERAGE_SIZE = 128
ROOF_HEIGHT_RANGE = 16.


def _footprint(house):
    """Use the exported ground corners, including the housekit's actual shear."""
    base = float(house['center'][1])
    points = {(float(p[0]), float(p[2])) for p in house['bounds_corners']
              if abs(float(p[1])-base) < .05}
    if len(points) < 3:
        raise ValueError('Missing ground footprint for '+str(house.get('id', 'house')))
    cx = sum(p[0] for p in points)/len(points)
    cz = sum(p[1] for p in points)/len(points)
    polygon = sorted(points, key=lambda p: math.atan2(p[1]-cz, p[0]-cx))
    height = max(float(p[1]) for p in house['bounds_corners'])
    return polygon, height


def _coverage_arrays(houses, size, extent, falloff):
    if not isinstance(size, int) or not 8 <= size <= 1024:
        raise ValueError('Coverage size must be an integer from 8 to 1024.')
    if not math.isfinite(extent) or extent <= 0 or not math.isfinite(falloff) or falloff <= 0:
        raise ValueError('Coverage extent and falloff must be positive finite metres.')
    cell = 2.*extent/size
    positions = -extent+(np.arange(size, dtype=np.float64)+.5)*cell
    coverage = np.zeros((size, size), dtype=np.float32)
    roof = np.zeros_like(coverage)
    for house in houses:
        polygon, height = _footprint(house)
        x0 = max(0, int(np.searchsorted(positions, min(p[0] for p in polygon)-falloff)))
        x1 = min(size, int(np.searchsorted(positions, max(p[0] for p in polygon)+falloff, side='right')))
        z0 = max(0, int(np.searchsorted(positions, min(p[1] for p in polygon)-falloff)))
        z1 = min(size, int(np.searchsorted(positions, max(p[1] for p in polygon)+falloff, side='right')))
        if x0 >= x1 or z0 >= z1:
            continue
        x = positions[None, x0:x1]; z = positions[z0:z1, None]
        distance_squared = np.full((z1-z0, x1-x0), np.inf)
        inside = np.ones(distance_squared.shape, dtype=bool)
        for a, b in zip(polygon, polygon[1:]+polygon[:1]):
            dx, dz = b[0]-a[0], b[1]-a[1]
            length_squared = dx*dx+dz*dz
            if length_squared < 1e-12:
                continue
            t = np.clip(((x-a[0])*dx+(z-a[1])*dz)/length_squared, 0., 1.)
            distance_squared = np.minimum(distance_squared,
                (x-a[0]-t*dx)**2+(z-a[1]-t*dz)**2)
            inside &= dx*(z-a[1])-dz*(x-a[0]) >= -1e-8
        distance = np.where(inside, 0., np.sqrt(distance_squared))
        t = np.clip(distance/falloff, 0., 1.)
        weight = (1.-t*t*(3.-2.*t)).astype(np.float32)
        target = coverage[z0:z1, x0:x1]; target_roof = roof[z0:z1, x0:x1]
        normalized_height = np.clip(height/ROOF_HEIGHT_RANGE, 0., 1.)
        # The highest nearby roof wins only when coverage ties. An unrelated
        # tall building must not set the height of a stronger adjacent bank.
        stronger = weight > target
        tied = (weight > 0.) & (abs(weight-target) < 1e-6)
        target_roof[:] = np.where(stronger, normalized_height,
            np.where(tied, np.maximum(target_roof, normalized_height), target_roof))
        np.maximum(target, weight, out=target)
    return coverage, roof


def build_coverage_pixels(size=COVERAGE_SIZE, extent=96., falloff=4.,
                          manifest_path=None, *, manifest=None):
    """Return (RGBA bytes, width, height), with no graphics/audio/file writes.

    Default bounds are COVERAGE_BOUNDS. A custom extent means the square
    [-extent,+extent] in both X and Z. The shader owns centre clearance and the
    outside-map fallback; this helper does not cut a circle into the field.
    ``manifest`` can supply an in-memory document for CPU tests/tools.
    """
    if manifest is None:
        path = Path(manifest_path) if manifest_path is not None else MANIFEST_PATH
        manifest = json.loads(path.read_text(encoding='utf-8'))
    coverage, roof = _coverage_arrays(manifest.get('houses', ()), size, float(extent), float(falloff))
    pixels = np.zeros((size, size, 4), dtype=np.uint8)
    pixels[:, :, 0] = np.rint(coverage*255).astype(np.uint8)
    pixels[:, :, 1] = np.rint(roof*255).astype(np.uint8)
    pixels[:, :, 3] = 255
    return pixels.tobytes(), size, size


def create_coverage_texture(**options):
    """Upload once; the caller owns and must unload the returned Texture2D.

    Native image memory is released after the synchronous upload. No borrowed
    Python buffer is passed to UnloadImage, and no audio device is opened.
    """
    import pyray as pr
    pixels, width, height = build_coverage_pixels(**options)
    memory = pr.rl.MemAlloc(len(pixels))
    if memory == pr.ffi.NULL:
        raise MemoryError('Cannot allocate canal fog coverage pixels.')
    pr.ffi.memmove(memory, pixels, len(pixels))
    image = pr.Image(memory, width, height, 1, pr.PIXELFORMAT_UNCOMPRESSED_R8G8B8A8)
    try:
        texture = pr.load_texture_from_image(image)
    finally:
        pr.unload_image(image)
    if not texture.id:
        raise RuntimeError('Cannot upload the canal fog coverage texture.')
    pr.set_texture_filter(texture, pr.TEXTURE_FILTER_BILINEAR)
    pr.set_texture_wrap(texture, pr.TEXTURE_WRAP_CLAMP)
    return texture


def check_coverage():
    """Fast independent CPU invariants; run this module directly to check them."""
    synthetic = dict(center=[12., .325, 3.],
        bounds_corners=[[x,y,z] for x in (9.,15.) for y in (.325,8.) for z in (1.,5.)])
    pixels, width, height = build_coverage_pixels(64,16.,4.,manifest={'houses':[synthetic]})
    image = np.frombuffer(pixels,dtype=np.uint8).reshape(height,width,4)
    def sample(x,z):
        return image[int((z+16.)/32.*height),int((x+16.)/32.*width)]
    assert sample(12.,3.)[0] == 255, 'House interior must have full coverage.'
    assert 0 < sample(7.,3.)[0] < 255, 'The exterior fringe must be smooth.'
    assert sample(4.,3.)[0] == 0, 'Coverage must end beyond four metres.'
    assert sample(12.,-8.)[0] == 0, 'Texture row direction must match world Z.'
    assert sample(12.,3.)[1] in (127,128), 'Eight-metre roof encodes to half height.'
    assert all(int(sample(x,3.)[0]) <= int(sample(x+.5,3.)[0]) for x in (4.,4.5,5.,5.5,6.,6.5,7.,7.5,8.)), 'Distance falloff must be monotonic.'
    assert np.all(image[:,:,3] == 255) and np.all(image[:,:,2] == 0)
    empty, _, _ = build_coverage_pixels(16,16.,4.,manifest={'houses':[]})
    assert not np.frombuffer(empty,dtype=np.uint8).reshape(16,16,4)[:,:,:3].any()
    actual, w, h = build_coverage_pixels()
    actual = np.frombuffer(actual,dtype=np.uint8).reshape(h,w,4)
    assert actual.shape == (COVERAGE_SIZE,COVERAGE_SIZE,4)
    assert actual[h//2,w//2,0] == 0, 'Authored pavilion centre must remain uncovered.'
    assert actual[:,:,0].max() == 255 and actual[:,:,0].min() == 0
    return dict(checks='passed', dimensions=[w,h], byte_count=actual.nbytes,
                covered_texels=int(np.count_nonzero(actual[:,:,0])))


if __name__ == '__main__':
    print(json.dumps(check_coverage()))
