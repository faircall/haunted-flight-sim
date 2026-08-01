from pathlib import Path

from PIL import Image


DIRECTION_SUFFIXES = {
    "_down": "R",
    "_up": "G",
    "_left": "B",
    "_right": "A",
}

SUPPORTED_EXTENSIONS = {".png"}


def parse_response_source(path):
    stem = path.stem

    for suffix in DIRECTION_SUFFIXES:
        if stem.endswith(suffix):
            base_name = stem[:-len(suffix)]
            direction = suffix[1:]
            return base_name, direction

    return None


def load_grayscale(path):
    with Image.open(path) as image:
        return image.convert("L").copy()


def validate_group(base_name, group):
    required = {"down", "up", "left", "right"}
    present = set(group)
    missing = required - present

    if missing:
        missing_text = ", ".join(sorted(missing))
        raise ValueError(f"{base_name}: missing directional textures: {missing_text}")

    sizes = {direction: image.size for direction, image in group.items()}
    unique_sizes = set(sizes.values())

    if len(unique_sizes) != 1:
        details = ", ".join(f"{direction}={size[0]}x{size[1]}" for direction, size in sorted(sizes.items()))
        raise ValueError(f"{base_name}: directional textures have mismatched sizes: {details}")


def pack_group(base_name, group, output_directory):
    validate_group(base_name, group)

    packed = Image.merge("RGBA", (
        group["down"],
        group["up"],
        group["left"],
        group["right"],
    ))

    output_path = output_directory / f"{base_name}.png"
    packed.save(output_path)

    print(f"packed: {base_name}")
    print(f"  R = {base_name}_down")
    print(f"  G = {base_name}_up")
    print(f"  B = {base_name}_left")
    print(f"  A = {base_name}_right")
    print(f"  -> {output_path}")


def collect_groups(input_directory):
    groups = {}

    for path in sorted(input_directory.iterdir()):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        parsed = parse_response_source(path)

        if parsed is None:
            raise ValueError(
                f"unexpected file in source folder: {path.name}\n"
                f"Expected names ending in _down.png, _up.png, _left.png, or _right.png"
            )

        base_name, direction = parsed
        group = groups.setdefault(base_name, {})

        if direction in group:
            raise ValueError(f"{base_name}: duplicate {direction} texture: {path.name}")

        group[direction] = load_grayscale(path)

    return groups


def pack_light_response_folder(input_directory, output_directory):
    input_directory = Path(input_directory)
    output_directory = Path(output_directory)

    if not input_directory.exists():
        raise FileNotFoundError(f"input directory does not exist: {input_directory}")

    if not input_directory.is_dir():
        raise NotADirectoryError(f"input path is not a directory: {input_directory}")

    output_directory.mkdir(parents=True, exist_ok=True)

    groups = collect_groups(input_directory)

    if not groups:
        raise ValueError(f"no directional response textures found in: {input_directory}")

    for base_name, group in sorted(groups.items()):
        pack_group(base_name, group, output_directory)

    print(f"finished: packed {len(groups)} response texture set(s)")


def main():
    input_directory = Path("artdev/light_response_directions")
    output_directory = Path("art/")

    pack_light_response_folder(input_directory, output_directory)


if __name__ == "__main__":
    main()