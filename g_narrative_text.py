"""UTF-8 font atlas and shared measurement/wrapping for narrative UI."""
from pathlib import Path
import re
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


def styled_characters(value):
    """Parse colour tags; unknown or unmatched tags remain visible as authored."""
    stack = [None]
    for part in re.split(r"(\[color=[^\]\n]+\]|\[/color\])", localize(value)):
        if part.startswith("[color=") and part[7:-1] in data.TEXT_COLORS:
            stack.append(part[7:-1])
        elif part == "[/color]" and len(stack) > 1:
            stack.pop()
        else:
            yield from ((char, stack[-1]) for char in part)


def plain_width(assets, value):
    return pr.measure_text_ex(font(assets, value), value, FONT_SIZE, 0).x


def width(assets, text):
    return plain_width(assets, "".join(char for char, _ in styled_characters(text)))


def draw(assets, text, x, y, color=None):
    characters = list(styled_characters(text))
    loaded = font(assets, "".join(char for char, _ in characters))
    base = pr.WHITE if color is None else color
    if isinstance(base, tuple):
        base = pr.Color(*base)
    # Measure the whole line prefix so spaces at colour boundaries retain their advance.
    from itertools import groupby
    prefix = ""
    for style, group in groupby(characters, key=lambda item: item[1]):
        value = "".join(char for char, _ in group)
        ink = pr.Color(*data.TEXT_COLORS[style], base.a) if style else base
        pr.draw_text_ex(loaded, value, pr.Vector2(x + plain_width(assets, prefix), y), FONT_SIZE, 0, ink)
        prefix += value


def encode_line(characters):
    """Make each wrapped line independently drawable, including continued colours."""
    result, active = [], None
    for char, style in characters:
        if style != active:
            if active:
                result.append("[/color]")
            if style:
                result.append("[color=" + style + "]")
            active = style
        result.append(char)
    if active:
        result.append("[/color]")
    return "".join(result)


def wrap(assets, text, maximum):
    """Measured Unicode wrapping, with basic CJK punctuation constraints."""
    lines = []
    closing = set("，。！？、；：）》】」』,.!?;:")
    opening = set("（《【「『(")
    paragraphs = [[]]
    for item in styled_characters(text):
        if item[0] == "\n":
            paragraphs.append([])
        else:
            paragraphs[-1].append(item)
    for paragraph in paragraphs:
        line = []
        for item in paragraph:
            char = item[0]
            visible = "".join(c for c, _ in line)
            if line and plain_width(assets, visible + char) > maximum and char not in closing:
                # Prefer an English word boundary; CJK can break between glyphs.
                split = visible.rfind(" ")
                if split > 0 and char.isascii() and char.isalpha():
                    lines.append(encode_line(line[:split]))
                    line = line[split + 1:]
                elif line[-1][0] in opening and len(line) > 1:
                    lines.append(encode_line(line[:-1]))
                    line = line[-1:]
                else:
                    lines.append(encode_line(line))
                    line = []
            line.append(item)
        lines.append(encode_line(line))
    return lines


def unload(assets):
    cache = assets.pop("narrative_font", {})
    if cache.get("font") is not None:
        pr.unload_font(cache["font"])
