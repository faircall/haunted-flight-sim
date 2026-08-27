import math


LIGHT_GEOMETRY_CACHE_VERSION = 1
LIGHT_GEOMETRY_RUNTIME_GENERATION = globals().get("LIGHT_GEOMETRY_RUNTIME_GENERATION", 0) + 1
EMPTY_SHAPE_CODE = 255
DDA_EPSILON = 0.000001
DEFAULT_POINT_RAY_COUNT = 128
DEFAULT_SPOT_RAY_COUNT = 64
DEFAULT_MAX_RAY_COUNT = 512
DEFAULT_CORNER_EPSILON = 0.0005
DEFAULT_POINT_CORNER_CANDIDATE_LIMIT = 16
DEFAULT_SPOT_CORNER_CANDIDATE_LIMIT = 12
DEFAULT_BUCKET_SIZE_TILES = 8


def tile_shape_local_vertices(shape_index, tile_width, tile_height):
    width = float(tile_width)
    height = float(tile_height)
    shapes = {
        0: [(0.0, 0.0), (width, 0.0), (width, height), (0.0, height)],
        1: [(0.0, 0.0), (width, 0.0), (0.0, height)],
        2: [(0.0, 0.0), (width, 0.0), (width, height)],
        3: [(width, 0.0), (width, height), (0.0, height)],
        4: [(0.0, 0.0), (width, height), (0.0, height)]
    }
    return shapes.get(int(shape_index), ())


def tile_shape_world_vertices(tile_x, tile_y, shape_index, tile_width, tile_height):
    origin_x = tile_x * tile_width
    origin_y = tile_y * tile_height
    return [{"x": origin_x + x, "y": origin_y + y} for x, y in tile_shape_local_vertices(shape_index, tile_width, tile_height)]


def canonical_edge(start, end):
    a = (float(start["x"]), float(start["y"]))
    b = (float(end["x"]), float(end["y"]))
    return (a, b) if a <= b else (b, a)


def build_light_collision_grid(tile_map, collidable_tile_indices):
    map_width = int(tile_map["map_width"])
    map_height = int(tile_map["map_height"])
    tile_width = int(tile_map["tile_width"])
    tile_height = int(tile_map["tile_height"])
    shape_codes = bytearray([EMPTY_SHAPE_CODE]) * (map_width * map_height)
    receiver_polygons = [None] * len(shape_codes)
    edge_counts = {}
    edge_values = {}

    for tile_index, tile in enumerate(tile_map["tiles"]):
        if tile.get("index", 0) not in collidable_tile_indices:
            continue

        tile_x = tile_index % map_width
        tile_y = tile_index // map_width
        shape_index = int(tile.get("shape_index", 0))
        vertices = tile_shape_world_vertices(tile_x, tile_y, shape_index, tile_width, tile_height)

        if len(vertices) < 3:
            continue

        shape_codes[tile_index] = shape_index
        receiver_polygons[tile_index] = vertices

        for vertex_index, start in enumerate(vertices):
            end = vertices[(vertex_index + 1) % len(vertices)]
            key = canonical_edge(start, end)
            edge_counts[key] = edge_counts.get(key, 0) + 1
            edge_values[key] = {"start": {"x": key[0][0], "y": key[0][1]}, "end": {"x": key[1][0], "y": key[1][1]}}

    boundary_segments = [edge_values[key] for key, count in edge_counts.items() if count == 1]
    vertex_lookup = {}
    boundary_vertices = []

    for segment in boundary_segments:
        for point in (segment["start"], segment["end"]):
            key = (point["x"], point["y"])

            if key not in vertex_lookup:
                vertex_lookup[key] = len(boundary_vertices)
                boundary_vertices.append({"x": point["x"], "y": point["y"]})

    bucket_size_tiles = DEFAULT_BUCKET_SIZE_TILES
    bucket_world_width = max(1, bucket_size_tiles * tile_width)
    bucket_world_height = max(1, bucket_size_tiles * tile_height)
    bucket_count_x = max(1, math.ceil(map_width / bucket_size_tiles))
    bucket_count_y = max(1, math.ceil(map_height / bucket_size_tiles))
    boundary_vertex_buckets = {}

    for vertex_index, vertex in enumerate(boundary_vertices):
        bucket_x = min(bucket_count_x - 1, max(0, int(vertex["x"] // bucket_world_width)))
        bucket_y = min(bucket_count_y - 1, max(0, int(vertex["y"] // bucket_world_height)))
        bucket_index = bucket_y * bucket_count_x + bucket_x
        boundary_vertex_buckets.setdefault(bucket_index, []).append(vertex_index)

    return {
        "cache_version": LIGHT_GEOMETRY_CACHE_VERSION,
        "runtime_generation": LIGHT_GEOMETRY_RUNTIME_GENERATION,
        "source_map_identity": id(tile_map),
        "geometry_revision": int(tile_map.get("geometry_revision", 0)),
        "map_width": map_width,
        "map_height": map_height,
        "tile_width": tile_width,
        "tile_height": tile_height,
        "shape_codes": shape_codes,
        "boundary_vertices": boundary_vertices,
        "boundary_segments": boundary_segments,
        "boundary_vertex_buckets": boundary_vertex_buckets,
        "bucket_size_tiles": bucket_size_tiles,
        "bucket_world_width": bucket_world_width,
        "bucket_world_height": bucket_world_height,
        "bucket_count_x": bucket_count_x,
        "bucket_count_y": bucket_count_y,
        "receiver_polygons": receiver_polygons,
        "shape_clip_planes": tuple(tile_shape_clip_planes(shape_index, tile_width, tile_height) for shape_index in range(5))
    }


def normalize_vector(vector):
    x = float(vector.get("x", 0.0))
    y = float(vector.get("y", 0.0))
    length = math.hypot(x, y)

    if length <= DDA_EPSILON:
        return None

    return {"x": x / length, "y": y / length}


def get_light_world_position(light, collision_grid):
    position = light.get("position", {})

    if "tile_x" in position and "tile_y" in position:
        return {
            "x": position.get("x", 0.0) + position.get("tile_x", 0) * collision_grid["tile_width"],
            "y": position.get("y", 0.0) + position.get("tile_y", 0) * collision_grid["tile_height"]
        }

    return {"x": float(position.get("x", 0.0)), "y": float(position.get("y", 0.0))}


def ray_map_interval(origin, direction, max_distance, collision_grid):
    minimum_x = 0.0
    minimum_y = 0.0
    maximum_x = collision_grid["map_width"] * collision_grid["tile_width"]
    maximum_y = collision_grid["map_height"] * collision_grid["tile_height"]
    interval_start = 0.0
    interval_end = float(max_distance)

    for origin_value, direction_value, minimum_value, maximum_value in (
        (origin["x"], direction["x"], minimum_x, maximum_x),
        (origin["y"], direction["y"], minimum_y, maximum_y)
    ):
        if abs(direction_value) <= DDA_EPSILON:
            if origin_value < minimum_value or origin_value > maximum_value:
                return None
            continue

        first = (minimum_value - origin_value) / direction_value
        second = (maximum_value - origin_value) / direction_value
        near = min(first, second)
        far = max(first, second)
        interval_start = max(interval_start, near)
        interval_end = min(interval_end, far)

        if interval_end < interval_start:
            return None

    if interval_end < 0.0 or interval_start > max_distance:
        return None

    return max(0.0, interval_start), min(float(max_distance), interval_end)


def outward_edge_normal(start, end):
    edge_x = end["x"] - start["x"]
    edge_y = end["y"] - start["y"]
    length = math.hypot(edge_x, edge_y)

    if length <= DDA_EPSILON:
        return {"x": 0.0, "y": 0.0}

    return {"x": edge_y / length, "y": -edge_x / length}


def tile_shape_clip_planes(shape_index, tile_width, tile_height):
    inverse_width = 1.0 / tile_width
    inverse_height = 1.0 / tile_height
    shapes = {
        0: ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (-1.0, 0.0, tile_width), (0.0, -1.0, tile_height)),
        1: ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (-inverse_width, -inverse_height, 1.0)),
        2: ((-1.0, 0.0, tile_width), (0.0, 1.0, 0.0), (inverse_width, -inverse_height, 0.0)),
        3: ((-1.0, 0.0, tile_width), (0.0, -1.0, tile_height), (inverse_width, inverse_height, -1.0)),
        4: ((1.0, 0.0, 0.0), (0.0, -1.0, tile_height), (-inverse_width, inverse_height, 0.0))
    }
    return shapes.get(int(shape_index), ())


def ray_intersect_tile_shape_values(origin_x, origin_y, direction_x, direction_y, tile_x, tile_y, shape_index, t_enter, t_exit, collision_grid):
    tile_width = collision_grid["tile_width"]
    tile_height = collision_grid["tile_height"]
    local_origin_x = origin_x - tile_x * tile_width
    local_origin_y = origin_y - tile_y * tile_height
    polygon_enter = -math.inf
    polygon_exit = math.inf
    enter_plane = -1
    enter_normal_x = -direction_x
    enter_normal_y = -direction_y

    clip_planes = collision_grid.get("shape_clip_planes")
    planes = clip_planes[shape_index] if clip_planes is not None else tile_shape_clip_planes(shape_index, tile_width, tile_height)

    for plane_index, (plane_x, plane_y, plane_offset) in enumerate(planes):
        offset = plane_x * local_origin_x + plane_y * local_origin_y + plane_offset
        rate = plane_x * direction_x + plane_y * direction_y

        if abs(rate) <= DDA_EPSILON:
            if offset < -DDA_EPSILON:
                return None
            continue

        boundary_t = -offset / rate

        if rate > 0.0:
            if boundary_t > polygon_enter:
                polygon_enter = boundary_t
                enter_plane = plane_index
                normal_length = math.hypot(plane_x, plane_y)
                enter_normal_x = -plane_x / normal_length
                enter_normal_y = -plane_y / normal_length
        elif boundary_t < polygon_exit:
            polygon_exit = boundary_t

        if polygon_exit < polygon_enter - DDA_EPSILON:
            return None

    hit_enter = max(float(t_enter), polygon_enter, 0.0)
    hit_exit = min(float(t_exit), polygon_exit)

    if hit_exit - hit_enter <= DDA_EPSILON:
        return None

    if polygon_enter < t_enter - DDA_EPSILON or enter_plane < 0:
        return max(0.0, hit_enter), -1, -direction_x, -direction_y

    return max(0.0, hit_enter), enter_plane, enter_normal_x, enter_normal_y


def ray_intersect_tile_shape(origin, direction, tile_x, tile_y, shape_index, t_enter, t_exit, collision_grid):
    hit = ray_intersect_tile_shape_values(origin["x"], origin["y"], direction["x"], direction["y"], tile_x, tile_y, shape_index, t_enter, t_exit, collision_grid)

    if hit is None:
        return None

    return {"distance": hit[0], "edge_index": hit[1], "normal": {"x": hit[2], "y": hit[3]}}


def dda_first_light_hit_values(origin_x, origin_y, direction_x, direction_y, max_distance, collision_grid):
    tile_width = collision_grid["tile_width"]
    tile_height = collision_grid["tile_height"]
    map_width = collision_grid["map_width"]
    map_height = collision_grid["map_height"]
    map_world_width = map_width * tile_width
    map_world_height = map_height * tile_height
    start_t = 0.0
    end_t = float(max_distance)

    for origin_value, direction_value, maximum_value in ((origin_x, direction_x, map_world_width), (origin_y, direction_y, map_world_height)):
        if abs(direction_value) <= DDA_EPSILON:
            if origin_value < 0.0 or origin_value > maximum_value:
                return None, 0
            continue

        first = -origin_value / direction_value
        second = (maximum_value - origin_value) / direction_value
        start_t = max(start_t, min(first, second))
        end_t = min(end_t, max(first, second))

        if end_t < start_t:
            return None, 0

    if end_t < 0.0 or start_t > max_distance:
        return None, 0

    start_t = max(0.0, start_t)
    end_t = min(float(max_distance), end_t)
    sample_t = min(end_t, start_t + DDA_EPSILON)
    sample_x = origin_x + direction_x * sample_t
    sample_y = origin_y + direction_y * sample_t
    tile_x = int(math.floor(sample_x / tile_width))
    tile_y = int(math.floor(sample_y / tile_height))
    tile_x = min(map_width - 1, max(0, tile_x))
    tile_y = min(map_height - 1, max(0, tile_y))
    step_x = 1 if direction_x > DDA_EPSILON else -1 if direction_x < -DDA_EPSILON else 0
    step_y = 1 if direction_y > DDA_EPSILON else -1 if direction_y < -DDA_EPSILON else 0
    delta_x = tile_width / abs(direction_x) if step_x else math.inf
    delta_y = tile_height / abs(direction_y) if step_y else math.inf

    if step_x > 0:
        maximum_x = ((tile_x + 1) * tile_width - origin_x) / direction_x
    elif step_x < 0:
        maximum_x = (tile_x * tile_width - origin_x) / direction_x
    else:
        maximum_x = math.inf

    if step_y > 0:
        maximum_y = ((tile_y + 1) * tile_height - origin_y) / direction_y
    elif step_y < 0:
        maximum_y = (tile_y * tile_height - origin_y) / direction_y
    else:
        maximum_y = math.inf

    current_t = start_t
    tile_steps = 0

    while 0 <= tile_x < map_width and 0 <= tile_y < map_height and current_t <= end_t + DDA_EPSILON:
        tile_steps += 1
        tile_exit = min(maximum_x, maximum_y, end_t)
        tile_index = tile_y * map_width + tile_x
        shape_index = collision_grid["shape_codes"][tile_index]

        if shape_index != EMPTY_SHAPE_CODE:
            if shape_index == 0 and tile_exit - current_t > DDA_EPSILON:
                hit_x = origin_x + direction_x * current_t - tile_x * tile_width
                hit_y = origin_y + direction_y * current_t - tile_y * tile_height
                edge_index = -1
                normal_x = -direction_x
                normal_y = -direction_y

                if current_t > DDA_EPSILON:
                    if abs(hit_x) <= DDA_EPSILON * 4.0:
                        edge_index, normal_x, normal_y = 3, -1.0, 0.0
                    elif abs(hit_x - tile_width) <= DDA_EPSILON * 4.0:
                        edge_index, normal_x, normal_y = 1, 1.0, 0.0
                    elif abs(hit_y) <= DDA_EPSILON * 4.0:
                        edge_index, normal_x, normal_y = 0, 0.0, -1.0
                    elif abs(hit_y - tile_height) <= DDA_EPSILON * 4.0:
                        edge_index, normal_x, normal_y = 2, 0.0, 1.0

                shape_hit = (max(0.0, current_t), edge_index, normal_x, normal_y)
            else:
                shape_hit = ray_intersect_tile_shape_values(origin_x, origin_y, direction_x, direction_y, tile_x, tile_y, shape_index, current_t, tile_exit, collision_grid)

            if shape_hit is not None and shape_hit[0] <= end_t + DDA_EPSILON:
                return (shape_hit[0], tile_x, tile_y, tile_index, int(shape_index), shape_hit[1], shape_hit[2], shape_hit[3]), tile_steps

        if tile_exit >= end_t - DDA_EPSILON:
            break

        if maximum_x < maximum_y - DDA_EPSILON:
            current_t = maximum_x
            maximum_x += delta_x
            tile_x += step_x
        elif maximum_y < maximum_x - DDA_EPSILON:
            current_t = maximum_y
            maximum_y += delta_y
            tile_y += step_y
        else:
            current_t = min(maximum_x, maximum_y)
            maximum_x += delta_x
            maximum_y += delta_y
            tile_x += step_x
            tile_y += step_y

    return None, tile_steps


def dda_first_light_hit(origin, direction, max_distance, collision_grid, stats=None):
    normalized_direction = normalize_vector(direction)

    if normalized_direction is None or max_distance <= 0.0:
        return None

    hit_values, tile_steps = dda_first_light_hit_values(origin["x"], origin["y"], normalized_direction["x"], normalized_direction["y"], max_distance, collision_grid)

    if stats is not None:
        stats["tile_steps"] = stats.get("tile_steps", 0) + tile_steps
        stats["max_tile_steps"] = max(stats.get("max_tile_steps", 0), tile_steps)

    if hit_values is None:
        return None

    distance, tile_x, tile_y, tile_index, shape_index, edge_index, normal_x, normal_y = hit_values
    return {
        "distance": distance,
        "point": {"x": origin["x"] + normalized_direction["x"] * distance, "y": origin["y"] + normalized_direction["y"] * distance},
        "tile_x": tile_x,
        "tile_y": tile_y,
        "tile_index": tile_index,
        "shape_index": shape_index,
        "edge_index": edge_index,
        "normal": {"x": normal_x, "y": normal_y},
        "dda_tile_steps": tile_steps
    }


def query_boundary_vertices(light_position, radius, collision_grid):
    bucket_width = collision_grid["bucket_world_width"]
    bucket_height = collision_grid["bucket_world_height"]
    bucket_count_x = collision_grid["bucket_count_x"]
    bucket_count_y = collision_grid["bucket_count_y"]
    minimum_bucket_x = max(0, int(math.floor((light_position["x"] - radius) / bucket_width)))
    maximum_bucket_x = min(bucket_count_x - 1, int(math.floor((light_position["x"] + radius) / bucket_width)))
    minimum_bucket_y = max(0, int(math.floor((light_position["y"] - radius) / bucket_height)))
    maximum_bucket_y = min(bucket_count_y - 1, int(math.floor((light_position["y"] + radius) / bucket_height)))
    vertex_indices = set()

    for bucket_y in range(minimum_bucket_y, maximum_bucket_y + 1):
        for bucket_x in range(minimum_bucket_x, maximum_bucket_x + 1):
            bucket_index = bucket_y * bucket_count_x + bucket_x
            vertex_indices.update(collision_grid["boundary_vertex_buckets"].get(bucket_index, ()))

    result = []

    for vertex_index in vertex_indices:
        vertex = collision_grid["boundary_vertices"][vertex_index]
        distance = math.hypot(vertex["x"] - light_position["x"], vertex["y"] - light_position["y"])

        if distance <= radius + DDA_EPSILON:
            result.append((distance, vertex))

    result.sort(key=lambda item: item[0])
    return result


def normalize_angle_signed(angle):
    return (angle + math.pi) % (math.pi * 2.0) - math.pi


def visibility_config_for_light(light, visibility_config=None):
    defaults = visibility_config or {}
    light_type = light.get("type", "point")
    default_count = defaults.get("spot_ray_count", DEFAULT_SPOT_RAY_COUNT) if light_type == "spot" else defaults.get("point_ray_count", DEFAULT_POINT_RAY_COUNT)
    return {
        "ray_count": max(1, int(light.get("visibility_ray_count", default_count))),
        "max_rays": max(1, int(light.get("visibility_max_rays", defaults.get("max_rays", DEFAULT_MAX_RAY_COUNT)))),
        "corner_rays": bool(light.get("visibility_corner_rays", defaults.get("corner_rays", True))),
        "corner_epsilon": max(0.0, float(light.get("visibility_corner_epsilon", defaults.get("corner_epsilon", DEFAULT_CORNER_EPSILON)))),
        "corner_candidate_limit": max(0, int(light.get("visibility_corner_candidate_limit", defaults.get("corner_candidate_limit", DEFAULT_SPOT_CORNER_CANDIDATE_LIMIT if light_type == "spot" else DEFAULT_POINT_CORNER_CANDIDATE_LIMIT))))
    }


def build_visibility_ray_angles(light, light_position, collision_grid, visibility_config=None):
    config = visibility_config_for_light(light, visibility_config)
    light_type = light.get("type", "point")
    maximum_rays = config["max_rays"]
    baseline_count = min(config["ray_count"], maximum_rays)
    radius = max(0.0, float(light.get("visibility_radius", light.get("radius", 100.0))))
    seen_angles = set()
    angles = []

    def add_angle(angle):
        normalized = angle % (math.pi * 2.0)
        key = round(normalized, 8)

        if key in seen_angles or len(angles) >= maximum_rays:
            return False

        seen_angles.add(key)
        angles.append(normalized)
        return True

    if light_type == "spot":
        direction = normalize_vector(light.get("direction", {"x": 1.0, "y": 0.0})) or {"x": 1.0, "y": 0.0}
        centre_angle = math.atan2(direction["y"], direction["x"])
        outer_angle = math.radians(float(light.get("outer_angle", 35.0)))

        if baseline_count == 1:
            add_angle(centre_angle)
        else:
            for ray_index in range(baseline_count):
                amount = ray_index / (baseline_count - 1)
                add_angle(centre_angle - outer_angle + amount * outer_angle * 2.0)
    else:
        centre_angle = 0.0
        outer_angle = math.pi

        for ray_index in range(baseline_count):
            add_angle((ray_index / baseline_count) * math.pi * 2.0)

    baseline_added = len(angles)
    boundary_candidates = query_boundary_vertices(light_position, radius, collision_grid) if config["corner_rays"] and config["corner_candidate_limit"] > 0 and len(angles) < maximum_rays else []
    filtered_candidates = []
    seen_candidate_directions = set()
    minimum_candidate_separation = (outer_angle * 2.0 / max(1, config["corner_candidate_limit"])) * 0.35

    for distance, vertex in boundary_candidates:
        angle = math.atan2(vertex["y"] - light_position["y"], vertex["x"] - light_position["x"])

        if light_type == "spot" and abs(normalize_angle_signed(angle - centre_angle)) > outer_angle + DDA_EPSILON:
            continue

        direction_key = round(angle % (math.pi * 2.0), 6)

        if direction_key in seen_candidate_directions:
            continue

        if any(abs(normalize_angle_signed(angle - accepted_angle)) < minimum_candidate_separation for candidate_distance, accepted_angle in filtered_candidates):
            continue

        seen_candidate_directions.add(direction_key)
        filtered_candidates.append((distance, angle))

        if len(filtered_candidates) >= config["corner_candidate_limit"]:
            break

    for distance, angle in filtered_candidates:
        for candidate_angle in (angle - config["corner_epsilon"], angle, angle + config["corner_epsilon"]):
            if light_type == "spot" and abs(normalize_angle_signed(candidate_angle - centre_angle)) > outer_angle + DDA_EPSILON:
                continue

            add_angle(candidate_angle)

            if len(angles) >= maximum_rays:
                break

        if len(angles) >= maximum_rays:
            break

    if light_type == "spot":
        angles.sort(key=lambda angle: normalize_angle_signed(angle - centre_angle))
    else:
        angles.sort()

    return {
        "angles": angles,
        "baseline_ray_count": baseline_added,
        "corner_candidate_count": len(filtered_candidates),
        "adaptive_rays_added": len(angles) - baseline_added
    }


def build_light_visibility_polygon_dda(light, light_position, collision_grid, visibility_config=None):
    radius = max(0.0, float(light.get("visibility_radius", light.get("radius", 100.0))))
    angle_data = build_visibility_ray_angles(light, light_position, collision_grid, visibility_config)
    shadow_bias = max(0.0, float(light.get("shadow_bias", 0.25)))
    polygon = []
    unbiased_polygon = []
    hit_tile_ids = set()
    dda_stats = {"tile_steps": 0, "max_tile_steps": 0}

    for angle in angle_data["angles"]:
        direction_x = math.cos(angle)
        direction_y = math.sin(angle)
        hit, tile_steps = dda_first_light_hit_values(light_position["x"], light_position["y"], direction_x, direction_y, radius, collision_grid)
        dda_stats["tile_steps"] += tile_steps
        dda_stats["max_tile_steps"] = max(dda_stats["max_tile_steps"], tile_steps)
        unbiased_distance = radius

        if hit is not None:
            unbiased_distance = hit[0]
            hit_tile_ids.add(hit[3])

        biased_distance = max(0.0, unbiased_distance - shadow_bias) if hit is not None else unbiased_distance
        unbiased_polygon.append({
            "x": light_position["x"] + direction_x * unbiased_distance,
            "y": light_position["y"] + direction_y * unbiased_distance
        })
        polygon.append({
            "x": light_position["x"] + direction_x * biased_distance,
            "y": light_position["y"] + direction_y * biased_distance
        })

    return {
        "polygon": polygon,
        "unbiased_polygon": unbiased_polygon,
        "hit_tile_ids": hit_tile_ids,
        "ray_count": len(angle_data["angles"]),
        "dda_tile_steps": dda_stats["tile_steps"],
        "max_dda_tile_steps_for_one_ray": dda_stats["max_tile_steps"],
        "corner_candidate_count": angle_data["corner_candidate_count"],
        "adaptive_rays_added": angle_data["adaptive_rays_added"],
        "baseline_ray_count": angle_data["baseline_ray_count"]
    }


def polygon_obviously_outside_spot(polygon, light_position, light):
    direction = normalize_vector(light.get("direction", {"x": 1.0, "y": 0.0})) or {"x": 1.0, "y": 0.0}
    centre_angle = math.atan2(direction["y"], direction["x"])
    outer_angle = math.radians(float(light.get("outer_angle", 35.0)))
    centre_x = sum(point["x"] for point in polygon) / len(polygon)
    centre_y = sum(point["y"] for point in polygon) / len(polygon)
    distance = math.hypot(centre_x - light_position["x"], centre_y - light_position["y"])

    if distance <= DDA_EPSILON:
        return False

    polygon_radius = max(math.hypot(point["x"] - centre_x, point["y"] - centre_y) for point in polygon)
    angular_margin = math.asin(min(1.0, polygon_radius / distance))
    angle = math.atan2(centre_y - light_position["y"], centre_x - light_position["x"])
    return abs(normalize_angle_signed(angle - centre_angle)) > outer_angle + angular_margin


def query_receiver_polygons(light_position, radius, collision_grid, light=None):
    tile_width = collision_grid["tile_width"]
    tile_height = collision_grid["tile_height"]
    map_width = collision_grid["map_width"]
    map_height = collision_grid["map_height"]
    minimum_x = max(0, math.floor((light_position["x"] - radius) / tile_width) - 1)
    maximum_x = min(map_width - 1, math.floor((light_position["x"] + radius) / tile_width) + 1)
    minimum_y = max(0, math.floor((light_position["y"] - radius) / tile_height) - 1)
    maximum_y = min(map_height - 1, math.floor((light_position["y"] + radius) / tile_height) + 1)
    receiver_tile_ids = []
    receiver_polygons = []

    for tile_y in range(minimum_y, maximum_y + 1):
        for tile_x in range(minimum_x, maximum_x + 1):
            tile_index = tile_y * map_width + tile_x
            polygon = collision_grid["receiver_polygons"][tile_index]

            if polygon is None:
                continue

            tile_min_x = tile_x * tile_width
            tile_min_y = tile_y * tile_height
            closest_x = min(tile_min_x + tile_width, max(tile_min_x, light_position["x"]))
            closest_y = min(tile_min_y + tile_height, max(tile_min_y, light_position["y"]))

            if (closest_x - light_position["x"]) ** 2 + (closest_y - light_position["y"]) ** 2 > radius * radius:
                continue

            if light is not None and light.get("type", "point") == "spot" and polygon_obviously_outside_spot(polygon, light_position, light):
                continue

            receiver_tile_ids.append(tile_index)
            receiver_polygons.append(polygon)

    return receiver_tile_ids, receiver_polygons


def make_light_geometry_key(light_record, world_position, collision_grid):
    light = light_record["light"]
    light_type = light.get("type", "point")
    config = visibility_config_for_light(light)
    direction = normalize_vector(light.get("direction", {"x": 1.0, "y": 0.0})) or {"x": 1.0, "y": 0.0}
    return (
        collision_grid["cache_version"],
        collision_grid.get("runtime_generation", 0),
        collision_grid["geometry_revision"],
        light_type,
        float(world_position["x"]),
        float(world_position["y"]),
        float(light.get("visibility_radius", light.get("radius", 100.0))),
        float(direction["x"]) if light_type == "spot" else None,
        float(direction["y"]) if light_type == "spot" else None,
        float(light.get("outer_angle", 35.0)) if light_type == "spot" else None,
        bool(light.get("casts_wall_shadows", light.get("casts_shadows", True))),
        float(light.get("shadow_bias", 0.25)),
        config["ray_count"],
        config["max_rays"],
        config["corner_rays"],
        config["corner_epsilon"],
        config["corner_candidate_limit"]
    )


def prune_light_visibility_cache(cache, current_frame, maximum_unused_frames):
    stale_ids = [light_id for light_id, entry in cache.items() if current_frame - entry.get("last_used_frame", current_frame) > maximum_unused_frames]

    for light_id in stale_ids:
        del cache[light_id]

    return len(stale_ids)


def light_ray_reaches_world_point(origin, world_point, collision_grid):
    to_point = {"x": world_point["x"] - origin["x"], "y": world_point["y"] - origin["y"]}
    distance = math.hypot(to_point["x"], to_point["y"])

    if distance <= DDA_EPSILON:
        return True

    hit = dda_first_light_hit(origin, to_point, distance, collision_grid)
    return hit is None or hit["distance"] >= distance - DDA_EPSILON


def light_reaches_world_point(light, world_point, collision_grid):
    return light_ray_reaches_world_point(get_light_world_position(light, collision_grid), world_point, collision_grid)


def smoothstep(edge_start, edge_end, value):
    if edge_end <= edge_start:
        return 1.0 if value >= edge_end else 0.0

    amount = max(0.0, min(1.0, (value - edge_start) / (edge_end - edge_start)))
    return amount * amount * (3.0 - 2.0 * amount)


def get_unoccluded_light_strength_at_world_point(light, world_point, collision_grid):
    if not light.get("enabled", True):
        return 0.0

    light_type = light.get("type", "point")
    light_position = get_light_world_position(light, collision_grid)

    if light_type == "top_down":
        size = light.get("size", {})
        half_width = max(0.0, float(size.get("x", 0.0))) * 0.5
        half_height = max(0.0, float(size.get("y", 0.0))) * 0.5

        if abs(world_point["x"] - light_position["x"]) > half_width or abs(world_point["y"] - light_position["y"]) > half_height:
            return 0.0

        return max(0.0, float(light.get("intensity", 1.0)))

    offset_x = world_point["x"] - light_position["x"]
    offset_y = world_point["y"] - light_position["y"]
    distance = math.hypot(offset_x, offset_y)
    radius = max(DDA_EPSILON, float(light.get("radius", 100.0)))

    if distance >= radius:
        return 0.0

    radial_strength = max(0.0, min(1.0, 1.0 - distance / radius)) ** max(DDA_EPSILON, float(light.get("falloff", 2.0)))
    cone_strength = 1.0

    if light_type == "spot" and distance > DDA_EPSILON:
        light_direction = normalize_vector(light.get("direction", {"x": 1.0, "y": 0.0})) or {"x": 1.0, "y": 0.0}
        alignment = offset_x / distance * light_direction["x"] + offset_y / distance * light_direction["y"]
        inner_angle = float(light.get("inner_angle", 20.0))
        outer_angle = max(inner_angle + DDA_EPSILON, float(light.get("outer_angle", 35.0)))
        cone_strength = smoothstep(math.cos(math.radians(outer_angle)), math.cos(math.radians(inner_angle)), alignment)

    near_strength = 1.0
    near_fade_distance = max(0.0, float(light.get("near_fade_distance", 0.0)))

    if near_fade_distance > 0.0:
        near_strength = smoothstep(0.0, near_fade_distance, distance)

    return radial_strength * cone_strength * near_strength * max(0.0, float(light.get("intensity", 1.0)))


def get_gameplay_light_strength_at_world_point(light, world_point, collision_grid):
    if not light.get("enabled", True) or not light.get("affects_ai", True):
        return 0.0

    strength = get_unoccluded_light_strength_at_world_point(light, world_point, collision_grid)

    if strength <= 0.0:
        return 0.0

    if light.get("type", "point") != "top_down" and not light_reaches_world_point(light, world_point, collision_grid):
        return 0.0

    return strength * max(0.0, float(light.get("gameplay_intensity", 1.0)))


def get_total_gameplay_light_strength_at_world_point(light_records, world_point, collision_grid):
    # Contributions add: this supports several weak lights combining into useful exposure.
    return sum(get_gameplay_light_strength_at_world_point(record.get("light", record), world_point, collision_grid) for record in light_records)
