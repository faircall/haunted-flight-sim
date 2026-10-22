"""Validated, atomic direction data for the Void Canals sequence editor.

The default profile reproduces V17. Loading is explicit: a missing or invalid
file raises DirectionError rather than replacing the author's settings with
defaults. Runtime code can retain its last valid profile and show that error.
No files are read or written at import time.

Bank scale applies to the authored cloud centre and dimensions, followed by
the world-space offset. Opacity multiplies individual alpha (the renderer
clamps the result). Camera keys are optional and disabled by default.
"""
from dataclasses import dataclass
from pathlib import Path
import json
import math
import os
import tempfile


VERSION = 1
DEFAULT_PATH = Path(__file__).resolve().parent / 'art/temple/huxin_canals/direction.json'
CUES = ('start', 'build_end', 'blend_end', 'middle_start', 'near_end',
        'far_start', 'middle_end', 'far_end', 'end')
CUE_LABELS = {
    'start': 'Puzzle activated',
    'build_end': 'Fog at full strength',
    'blend_end': 'World revealed / near fog clears',
    'middle_start': 'Middle fog starts clearing',
    'near_end': 'Near fog mostly clear',
    'far_start': 'Far fog starts clearing',
    'middle_end': 'Middle fog mostly clear',
    'far_end': 'Far fog mostly clear',
    'end': 'Last traces gone',
}
BANDS = ('near', 'middle', 'far')
DEFAULT_CUE_TIMES = (0., 5., 6., 12., 14., 20., 22., 32., 46.)
MIN_CUE_SPACING = .1
MAX_DURATION = 1800.
MIN_SCALE, MAX_SCALE = .1, 5.
MIN_OPACITY, MAX_OPACITY = 0., 2.
DEFAULT_CAMERA_EYE = (4.05, 3.2, 3.05)
DEFAULT_CAMERA_TARGET = (-.7, 1.5, -1.2)
DEFAULT_CAMERA_FOV = 78.


class DirectionError(ValueError):
    """An authoring or file error that should be shown to the editor user."""


@dataclass(frozen=True, slots=True)
class BandPlacement:
    offset: tuple[float, float, float]
    scale: float
    opacity: float


@dataclass(frozen=True, slots=True)
class CameraPose:
    eye: tuple[float, float, float]
    target: tuple[float, float, float]
    fov: float


@dataclass(frozen=True, slots=True)
class CameraKey:
    cue: str
    eye: tuple[float, float, float]
    target: tuple[float, float, float]
    fov: float


@dataclass(frozen=True, slots=True)
class DirectionProfile:
    """A cache-safe runtime snapshot; use profile_from_document to create it."""
    cue_times: tuple[float, ...]
    bank_settings: tuple[BandPlacement, ...]
    camera_enabled: bool
    camera_keys: tuple[CameraKey, ...]

    def cue(self, name):
        try:return self.cue_times[CUES.index(name)]
        except ValueError:raise KeyError(name) from None

    def time(self, name):
        return self.cue(name)

    def band(self, name):
        try:return self.bank_settings[BANDS.index(name)]
        except ValueError:raise KeyError(name) from None

    def camera(self, name):
        if name not in CUES:raise KeyError(name)
        return next((key for key in self.camera_keys if key.cue == name), None)


def default_document():
    """Return an independently editable JSON document with exact V17 values."""
    return {
        'version': VERSION,
        'cues': dict(zip(CUES, DEFAULT_CUE_TIMES)),
        'banks': {name: {'offset': [0., 0., 0.], 'scale': 1., 'opacity': 1.}
                  for name in BANDS},
        'cameras': {'enabled': False, 'keys': {
            name: {'eye': list(DEFAULT_CAMERA_EYE),
                   'target': list(DEFAULT_CAMERA_TARGET), 'fov': DEFAULT_CAMERA_FOV}
            for name in CUES}},
    }


def _object(value, path, required, optional=()):
    if not isinstance(value, dict):raise DirectionError(f'{path}: expected an object')
    missing = set(required) - value.keys()
    unknown = value.keys() - set(required) - set(optional)
    if missing:raise DirectionError(f'{path}: missing {", ".join(sorted(missing))}')
    if unknown:raise DirectionError(f'{path}: unknown field {", ".join(sorted(map(str, unknown)))}')
    return value


def _number(value, path, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DirectionError(f'{path}: expected a finite number')
    try:value = float(value)
    except (OverflowError, ValueError):raise DirectionError(f'{path}: expected a finite number') from None
    if not math.isfinite(value):raise DirectionError(f'{path}: expected a finite number')
    if not low <= value <= high:
        raise DirectionError(f'{path}: must be between {low:g} and {high:g}')
    return value


def _vector(value, path):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise DirectionError(f'{path}: expected three coordinates [x, y, z]')
    return [_number(v, f'{path}[{i}]', -1000., 1000.) for i, v in enumerate(value)]


def validate_document(document):
    """Validate and return a fresh normalized copy without mutating the input."""
    doc = _object(document, 'direction', ('version', 'cues', 'banks', 'cameras'))
    if isinstance(doc['version'], bool) or not isinstance(doc['version'], int) or doc['version'] != VERSION:
        raise DirectionError(f'version: expected supported version {VERSION}')
    cue_data = _object(doc['cues'], 'cues', CUES)
    cues = {name: _number(cue_data[name], f'cues.{name}', 0., MAX_DURATION) for name in CUES}
    if cues['start'] != 0.:raise DirectionError('cues.start: must remain zero')
    for before, after in zip(CUES, CUES[1:]):
        if cues[after] - cues[before] < MIN_CUE_SPACING - 1e-9:
            raise DirectionError(f'cues.{after}: must be at least {MIN_CUE_SPACING:g}s after {before}')

    bank_data = _object(doc['banks'], 'banks', BANDS)
    banks = {}
    for name in BANDS:
        path = f'banks.{name}'
        bank = _object(bank_data[name], path, ('offset', 'scale', 'opacity'))
        banks[name] = {
            'offset': _vector(bank['offset'], f'{path}.offset'),
            'scale': _number(bank['scale'], f'{path}.scale', MIN_SCALE, MAX_SCALE),
            'opacity': _number(bank['opacity'], f'{path}.opacity', MIN_OPACITY, MAX_OPACITY),
        }

    camera_data = _object(doc['cameras'], 'cameras', ('enabled', 'keys'))
    if not isinstance(camera_data['enabled'], bool):
        raise DirectionError('cameras.enabled: expected true or false')
    key_data = _object(camera_data['keys'], 'cameras.keys', (), CUES)
    if camera_data['enabled'] and not key_data:
        raise DirectionError('cameras.keys: add a camera key before enabling authored cameras')
    keys = {}
    for name in CUES:
        if name not in key_data:continue
        path = f'cameras.keys.{name}'
        key = _object(key_data[name], path, ('eye', 'target', 'fov'))
        eye, target = _vector(key['eye'], f'{path}.eye'), _vector(key['target'], f'{path}.target')
        if math.dist(eye, target) < .01:
            raise DirectionError(f'{path}.target: must be distinct from the camera eye (at least .01m)')
        keys[name] = {'eye': eye, 'target': target,
                      'fov': _number(key['fov'], f'{path}.fov', 15., 110.)}
    # Eye and target can be valid at both endpoints yet coincide between
    # them. The eased path follows this same segment, so check its closest
    # point analytically rather than allowing a singular runtime camera.
    for (name_a, a), (name_b, b) in zip(keys.items(), list(keys.items())[1:]):
        direction = [t-e for t, e in zip(a['target'], a['eye'])]
        change = [t-e-d for t, e, d in zip(b['target'], b['eye'], direction)]
        length2 = sum(v*v for v in change)
        t = max(0., min(1., -sum(d*v for d, v in zip(direction, change))/length2)) if length2 else 0.
        closest = math.sqrt(sum((d+t*v)**2 for d, v in zip(direction, change)))
        if closest < .01:
            raise DirectionError(f'cameras.keys.{name_b}: camera path from {name_a} crosses its target; add an intermediate key')
    return {'version': VERSION, 'cues': cues, 'banks': banks,
            'cameras': {'enabled': camera_data['enabled'], 'keys': keys}}


def profile_from_document(document):
    doc = validate_document(document)
    return DirectionProfile(
        tuple(doc['cues'][name] for name in CUES),
        tuple(BandPlacement(tuple(doc['banks'][name]['offset']), doc['banks'][name]['scale'],
                            doc['banks'][name]['opacity']) for name in BANDS),
        doc['cameras']['enabled'],
        tuple(CameraKey(name, tuple(key['eye']), tuple(key['target']), key['fov'])
              for name, key in doc['cameras']['keys'].items()))


def document_from_profile(profile):
    if not isinstance(profile, DirectionProfile):raise DirectionError('profile: expected DirectionProfile')
    return validate_document({
        'version': VERSION,
        'cues': dict(zip(CUES, profile.cue_times)),
        'banks': {name: {'offset': list(bank.offset), 'scale': bank.scale, 'opacity': bank.opacity}
                  for name, bank in zip(BANDS, profile.bank_settings)},
        'cameras': {'enabled': profile.camera_enabled, 'keys': {
            key.cue: {'eye': list(key.eye), 'target': list(key.target), 'fov': key.fov}
            for key in profile.camera_keys}},
    })


DEFAULT_DIRECTION = profile_from_document(default_document())
DEFAULT_PROFILE = DEFAULT_DIRECTION


def sample_camera(profile, elapsed, *, include_disabled=False):
    """Interpolate authored keys with zero velocity at each cue; hold the ends.

    Disabled cameras return None unless an editor explicitly requests a
    preview. Partial key sets are allowed, using their actual cue timestamps.
    """
    if not profile.camera_enabled and not include_disabled:return None
    if not profile.camera_keys:return None
    elapsed = _number(elapsed, 'camera sample time', -MAX_DURATION, MAX_DURATION * 2.)
    keys = profile.camera_keys
    if elapsed <= profile.cue(keys[0].cue):
        key = keys[0]
        return CameraPose(key.eye, key.target, key.fov)
    for a, b in zip(keys, keys[1:]):
        end = profile.cue(b.cue)
        if elapsed > end:continue
        start = profile.cue(a.cue)
        t = max(0., min(1., (elapsed - start) / (end - start)))
        t = t*t*t*(t*(t*6.-15.)+10.)
        eye = tuple(x+(y-x)*t for x, y in zip(a.eye, b.eye))
        target = tuple(x+(y-x)*t for x, y in zip(a.target, b.target))
        return CameraPose(eye, target, a.fov+(b.fov-a.fov)*t)
    key = keys[-1]
    return CameraPose(key.eye, key.target, key.fov)


def _path(path):
    return DEFAULT_PATH if path is None else Path(path).expanduser().resolve()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:raise DirectionError(f'JSON: duplicate field {key!r}')
        result[key] = value
    return result


def load_direction(path=None):
    """Read saved values or raise a specific, displayable error; never fallback."""
    path = _path(path)
    try:
        with path.open('r', encoding='utf-8') as stream:
            document = json.load(stream, object_pairs_hook=_unique_object)
        return validate_document(document)
    except (OSError, UnicodeError, ValueError) as exc:
        raise DirectionError(f'Cannot load direction from {path}: {exc}') from exc


def save_direction(document, path=None):
    """Validate first, then replace the complete file atomically using UTF-8/LF."""
    normalized = validate_document(document)
    path = _path(path)
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', newline='\n',
                                         dir=path.parent, prefix=f'.{path.name}.',
                                         suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(normalized, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
    except OSError as exc:
        raise DirectionError(f'Cannot save direction to {path}: {exc}') from exc
    finally:
        if temporary is not None:
            try:temporary.unlink(missing_ok=True)
            except OSError:pass
    return path
