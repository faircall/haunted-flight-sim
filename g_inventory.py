"""Fixed slots, atomic transfers and procedural item use. No rendering."""
import copy
import g_interaction_data as data


def add(slots, item):
    """All-or-nothing insertion. Metadata distinguishes different puzzle keys."""
    pending = copy.deepcopy(slots)
    remaining = int(item.get("count", 1))
    if remaining <= 0:
        return False
    limit = max(1, int(data.ITEMS[item["kind"]]["stack"]))
    signature = {k: v for k, v in item.items() if k != "count"}
    order = [i for i, s in enumerate(pending) if s is not None] + [i for i, s in enumerate(pending) if s is None]
    for i in order:
        slot = pending[i]
        if slot is not None and {k: v for k, v in slot.items() if k != "count"} != signature:
            continue
        amount = min(remaining, limit - (slot["count"] if slot else 0))
        if amount <= 0:
            continue
        pending[i] = dict(signature, count=(slot["count"] if slot else 0) + amount)
        remaining -= amount
        if not remaining:
            slots[:] = pending
            return True
    return False


def count(slots, kind):
    return sum(s["count"] for s in slots if s and s["kind"] == kind)


def consume(slots, kind, amount):
    if amount < 0 or count(slots, kind) < amount:
        return False
    for i, slot in enumerate(slots):
        if slot and slot["kind"] == kind:
            taken = min(amount, slot["count"])
            slot["count"] -= taken
            amount -= taken
            if not slot["count"]:
                slots[i] = None
    return True


def ensure(arena):
    player = arena["player_info"]
    if "inventory" not in player:
        slots = [None] * data.SLOT_COUNT
        # Preserve old saves, including unusually large debug ammo reserves.
        items = [{"kind": "ammo", "count": int(player.get("ammo", {}).get("spare_pistol", 0))}]
        items += [{"kind": "key", "group": str(group), "count": int(n)}
                  for group, n in arena["puzzle_state"]["inventory"].items()]
        overflow = []
        for item in items:
            remaining = item["count"]
            while remaining > 0:
                amount = min(remaining, data.ITEMS[item["kind"]]["stack"])
                chunk = dict(item, count=amount)
                if not add(slots, chunk):
                    overflow.append(chunk)
                remaining -= amount
        player["inventory"] = slots
        player["inventory_overflow"] = overflow
    # Legacy overflow remains explicit and can be claimed after making space.
    sync_ammo(player)
    return arena


def sync_ammo(player):
    player.setdefault("ammo", {})["spare_pistol"] = count(player["inventory"], "ammo")


def use(player, index):
    slots = player["inventory"]
    item = slots[index]
    if not item or item["kind"] != "health":
        return "automatic_item"
    maximum = player.get("max_health", 100)
    if player["health"] >= maximum:
        return "healthy"
    player["health"] = min(maximum, player["health"] + item.get("value", 25))
    item["count"] -= 1
    if not item["count"]:
        slots[index] = None
    return "healed"
