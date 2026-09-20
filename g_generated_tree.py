"""Independent procedural foliage experiment; never rewrites the authored art."""
import math
import random
from pathlib import Path

from PIL import Image
import g_tree_animation as rig

ART = Path(__file__).resolve().parent / "art" / "split_tree"


def build(seed=17, density=1.3):
    """Use painted coverage to place strands; sample leaf colours once at rest."""
    rng = random.Random(seed)
    strands = []
    spacing = 2.2 / max(.5, density)
    for part in rig.PARTS:
        with Image.open(ART / f"willow_tree_{part['name']}.png") as source:
            art = source.convert("RGBA")
        left, top, right, bottom = part["bounds"]
        x = left + spacing * .5
        while x < right:
            column = max(left, min(right-1, round(x)))
            occupied = [y for y in range(top, bottom) if art.getpixel((column, y))[3] > 100]
            if len(occupied) >= 3:
                shoulder = (x, min(occupied))
                tip = (x + rng.uniform(-.8, .8), max(occupied) + .5)
                leaves = []
                y = shoulder[1] + rng.random()
                while y <= tip[1]:
                    # Keep holes in the reference; resolve a near-transparent sample locally.
                    candidates = [(column+dx, round(y)) for dx in (0, -1, 1)
                                  if left <= column+dx < right and top <= round(y) < bottom]
                    sample = next((p for p in candidates if art.getpixel(p)[3] > 100), None)
                    if sample:
                        rgb = art.getpixel(sample)[:3]
                        t = (y-shoulder[1])/max(1., tip[1]-shoulder[1])
                        fullness = 1. + .65 * (1.-t)**2
                        leaves.append(dict(t=t,
                            offset=rng.uniform(-.65, .65), length=rng.uniform(1.7, 3.5),
                            width=rng.uniform(.85, 1.55)*fullness, turn=rng.uniform(-.7, .7),
                            normal=rng.uniform(0, math.tau), fill=rng.uniform(.68, .79), color=rgb))
                    y += rng.uniform(1.15, 1.9)
                if leaves:
                    strands.append(dict(part=part, shoulder=shoulder, tip=tip, leaves=leaves,
                        phase=rng.uniform(0, math.tau), freedom=rng.uniform(.75, 1.25)))
            x += spacing
    return strands


def point(strand, t, elapsed, angle, bend, energy):
    """A rooted curve through its crown shoulder and down to the hanging tip."""
    root = strand["part"]["pivot"]
    shoulder, tip = strand["shoulder"], strand["tip"]
    if t < 0:
        # t=-1 is the branch root; t=0 is the crown shoulder.
        u = max(0., t+1.)
        x = root[0] + (shoulder[0]-root[0])*u
        y = root[1] + (shoulder[1]-root[1])*u - math.sin(u*math.pi)*2.
        weight = u * .18
    else:
        x = shoulder[0] + (tip[0]-shoulder[0])*t
        y = shoulder[1] + (tip[1]-shoulder[1])*t
        weight = .18 + .82*t*t
    phase = strand["phase"]
    sway = (math.sin(elapsed*1.25 + phase - max(0., t)*.7) +
            .3*math.sin(elapsed*2.1 + phase*1.4))
    x += energy * strand["freedom"] * weight * 1.8 * sway
    y += energy * weight * .22 * math.sin(elapsed*1.5 + phase)
    return rig.deform_point((x,y), strand["part"], angle, bend)


def pose(strands, elapsed, profile, still=False):
    """Return stem segments and diamond leaves with stable colour/normal identities."""
    poses = {p["name"]: rig.motion(p, elapsed, profile, mode="still" if still else "hybrid")
             for p in rig.PARTS}
    wind = rig.irregular_wind(profile, (0., 0.), elapsed)
    energy = 0. if still else min(1.5, math.hypot(wind["x"],wind["y"])/8.)
    stems, leaves = [], []
    for strand in strands:
        angle,bend = poses[strand["part"]["name"]]
        curve = [point(strand,i/32.,elapsed,angle,bend,energy) for i in range(33)]
        def sample(t):
            u = min(32.,max(0.,t*32.))
            index = min(31,int(u))
            blend = u-index
            a,b = curve[index],curve[index+1]
            return a[0]+(b[0]-a[0])*blend,a[1]+(b[1]-a[1])*blend
        # Keep the hidden crown connections unobtrusive; no dark spokes over the art.
        previous = sample(0.)
        for i in range(1, 13):
            current = sample(i/12.)
            stems.append((previous,current))
            previous = current
        for leaf in strand["leaves"]:
            t = leaf["t"]
            x,y = sample(t)
            before,after = sample(max(0.,t-.02)),sample(min(1.,t+.02))
            direction = math.atan2(after[1]-before[1], after[0]-before[0]) + leaf["turn"]
            turn = energy*.16*math.sin(elapsed*1.4+strand["phase"]+t*2.)
            direction += turn
            dx,dy = math.cos(direction),math.sin(direction)
            x += leaf["offset"]
            half = leaf["length"]*.5
            width = leaf["width"]*.5
            quad = ((x-dx*half,y-dy*half),(x-dy*width,y+dx*width),
                    (x+dx*half,y+dy*half),(x+dy*width,y-dx*width))
            leaves.append((quad,leaf["color"],leaf["normal"]+angle+turn,leaf["fill"]))
    return stems,leaves
