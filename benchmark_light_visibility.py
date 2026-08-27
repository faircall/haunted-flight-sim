import math
import statistics
import time

import g_light_visibility as visibility


def make_dense_wall_map(width=64, height=48, tile_size=16):
    tiles = []

    for tile_y in range(height):
        for tile_x in range(width):
            border = tile_x in (0, width - 1) or tile_y in (0, height - 1)
            vertical_maze = tile_x % 6 == 0 and tile_y % 7 not in (2, 3)
            horizontal_maze = tile_y % 6 == 0 and tile_x % 9 not in (4, 5)
            solid = border or vertical_maze or horizontal_maze
            shape_index = (tile_x + tile_y) % 5 if solid and (tile_x + tile_y) % 4 == 0 else 0
            tiles.append({"index": 1 if solid else 0, "shape_index": shape_index})

    return {
        "map_width": width,
        "map_height": height,
        "tile_width": tile_size,
        "tile_height": tile_size,
        "geometry_revision": 0,
        "tiles": tiles
    }


def make_stress_lights():
    records = []

    for index in range(6):
        records.append({
            "id": f"enemy:{index}:torch",
            "light": {
                "type": "point", "position": {"x": 140.0 + index * 90.0, "y": 120.0 + index * 35.0},
                "radius": 180.0, "casts_wall_shadows": True, "shadow_bias": 0.25,
                "mobility": "dynamic", "intensity": 1.0
            }
        })

    for index in range(2):
        records.append({
            "id": f"enemy:{index}:flashlight",
            "light": {
                "type": "spot", "position": {"x": 200.0 + index * 280.0, "y": 330.0},
                "direction": {"x": 1.0, "y": 0.0}, "outer_angle": 27.0,
                "radius": 210.0, "casts_wall_shadows": True, "shadow_bias": 0.25,
                "mobility": "dynamic", "intensity": 1.0
            }
        })

    records.append({
        "id": "runtime:player_flashlight",
        "light": {
            "type": "spot", "position": {"x": 390.0, "y": 210.0},
            "direction": {"x": 1.0, "y": 0.0}, "outer_angle": 27.0,
            "radius": 180.0, "casts_wall_shadows": True, "shadow_bias": 0.25,
            "mobility": "dynamic", "intensity": 1.2
        }
    })

    for index in range(4):
        records.append({
            "id": f"static:{index}:lamp",
            "light": {
                "type": "point", "position": {"x": 160.0 + index * 190.0, "y": 560.0},
                "radius": 170.0, "casts_wall_shadows": True, "shadow_bias": 0.25,
                "mobility": "static", "intensity": 1.0
            }
        })

    for index in range(12):
        records.append({
            "id": f"effect:{index}",
            "light": {
                "type": "point", "position": {"x": 80.0 + index * 65.0, "y": 420.0},
                "radius": 90.0, "casts_wall_shadows": False,
                "mobility": "transient", "intensity": 2.0
            }
        })

    return records


def percentile_95(values):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(len(ordered) * 0.95) - 1)]


def run_scenario(collision_grid, base_records, move_dynamic, iterations=120):
    cache = {}
    times_ms = []
    total_rays = 0
    total_steps = 0
    hits = 0
    misses = 0

    for frame in range(iterations):
        started = time.perf_counter()

        for record in base_records:
            light = dict(record["light"])
            light["position"] = dict(light["position"])
            light["intensity"] = 0.75 + 0.25 * math.sin(frame * 0.31 + len(record["id"]))

            if move_dynamic and light.get("mobility") == "dynamic":
                light["position"]["x"] += math.sin(frame * 0.09 + len(record["id"])) * 18.0
                light["position"]["y"] += math.cos(frame * 0.07 + len(record["id"])) * 13.0

                if light["type"] == "spot":
                    angle = frame * 0.035 + len(record["id"])
                    light["direction"] = {"x": math.cos(angle), "y": math.sin(angle)}

            if not light.get("casts_wall_shadows", True) or light["type"] == "top_down":
                continue

            current_record = {"id": record["id"], "light": light}
            world_position = visibility.get_light_world_position(light, collision_grid)
            geometry_key = visibility.make_light_geometry_key(current_record, world_position, collision_grid)
            cache_entry = cache.get(record["id"])

            if cache_entry is not None and cache_entry["geometry_key"] == geometry_key:
                hits += 1
                continue

            geometry = visibility.build_light_visibility_polygon_dda(light, world_position, collision_grid)
            cache[record["id"]] = {"geometry_key": geometry_key, "geometry": geometry}
            misses += 1
            total_rays += geometry["ray_count"]
            total_steps += geometry["dda_tile_steps"]

        times_ms.append((time.perf_counter() - started) * 1000.0)

    solve_count = max(1, misses)
    lookup_count = max(1, hits + misses)
    return {
        "mean_ms": statistics.mean(times_ms),
        "median_ms": statistics.median(times_ms),
        "p95_ms": percentile_95(times_ms),
        "cpu_only_fps": 1000.0 / statistics.mean(times_ms),
        "cache_hit_rate": hits / lookup_count,
        "visibility_rebuilds": misses,
        "average_rays_per_rebuild": total_rays / solve_count,
        "average_dda_steps_per_rebuild": total_steps / solve_count,
        "average_dda_steps_per_ray": total_steps / max(1, total_rays)
    }


def print_result(name, result):
    print(name)

    for key, value in result.items():
        print(f"  {key}: {value:.3f}")


def main():
    tile_map = make_dense_wall_map()
    collision_grid = visibility.build_light_collision_grid(tile_map, {1})
    records = make_stress_lights()
    static_result = run_scenario(collision_grid, records, False)
    moving_result = run_scenario(collision_grid, records, True)
    print(f"dense map: {collision_grid['map_width']}x{collision_grid['map_height']}, exposed vertices: {len(collision_grid['boundary_vertices'])}")
    print("lights: 6 moving points, 3 moving spots, 4 static shadowed points, 12 unshadowed transients")
    print_result("stationary geometry (intensity flicker only)", static_result)
    print_result("moving/rotating geometry", moving_result)
    print("cpu_only_fps measures visibility preparation throughput only; it is not rendered game FPS.")


if __name__ == "__main__":
    main()
