"""UTF-8 font atlas and shared measurement/wrapping for narrative UI."""
from pathlib import Path
import pyray as pr
import g_interaction_data as data

# Fusion Pixel's 12px grid occupies 16px including its vertical font metrics.
FONT_SIZE = 16


def localize(value):
    if isinstance(value, dict):
        return value.get(data.LANGUAGE, value.get("en", next(iter(value.values()), "")))
    return localize(data.TEXT[value]) if value in data.TEXT else str(value)


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from strings(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from strings(v)


def font(assets, extra=""):
    variant = "zh_hant" if data.LANGUAGE == "zh_hant" else "zh_hans"
    path = Path(__file__).parent / "fonts" / f"fusion-pixel-12px-proportional-{variant}.ttf"
    stamp = path.stat().st_mtime_ns if path.exists() else 0
    cache = assets.setdefault("narrative_font", {})
    required = set(range(32, 127)) | {ord(c) for c in extra}
    if not cache:
        required |= {ord(c) for s in strings((data.TEXT, data.DESCRIPTIONS, data.ITEMS)) for c in s}
    if cache.get("key") != (str(path), stamp, FONT_SIZE) or not required.issubset(cache.get("glyphs", set())):
        required |= cache.get("glyphs", set())
        if cache.get("font") is not None:
            pr.rl_draw_render_batch_active()
            pr.unload_font(cache["font"])
        if not stamp:
            raise FileNotFoundError(f"Narrative font missing: {path}")
        codes = sorted(required - {10, 13})
        codepoints = pr.ffi.new("int[]", codes)
        loaded = pr.load_font_ex(str(path), FONT_SIZE, pr.ffi.cast("int *", codepoints), len(codes))
        pr.set_texture_filter(loaded.texture, pr.TextureFilter.TEXTURE_FILTER_POINT)
        cache.update(key=(str(path), stamp, FONT_SIZE), glyphs=required, font=loaded)
    return cache["font"]


def width(assets, text):
    return pr.measure_text_ex(font(assets, text), text, FONT_SIZE, 0).x


def draw(assets, text, x, y, color=None):
    text = localize(text)
    pr.draw_text_ex(font(assets, text), text, pr.Vector2(x, y), FONT_SIZE, 0, color or pr.WHITE)


def wrap(assets, text, maximum):
    """Measured Unicode wrapping, with basic CJK punctuation constraints."""
    lines = []
    closing = set("，。！？、；：）》】」』,.!?;:")
    opening = set("（《【「『(")
    for paragraph in localize(text).split("\n"):
        line = ""
        for char in paragraph:
            if line and width(assets, line + char) > maximum and char not in closing:
                # Prefer an English word boundary; CJK can break between glyphs.
                split = line.rfind(" ")
                if split > 0 and char.isascii() and char.isalpha():
                    lines.append(line[:split])
                    line = line[split + 1:]
                elif line[-1] in opening and len(line) > 1:
                    lines.append(line[:-1])
                    line = line[-1]
                else:
                    lines.append(line)
                    line = ""
            line += char
        lines.append(line)
    return lines


def unload(assets):
    cache = assets.pop("narrative_font", {})
    if cache.get("font") is not None:
        pr.unload_font(cache["font"])
