"""Rebuilt adult character with connected trousers and a deliberately small atlas.

Z-up, facing -Y. One skinned mesh, fifteen existing bones, no subdivision.
Continuous sleeves and multiple weighted joint rings preserve the silhouette.
"""
import math
from mathutils import Vector
from player_texture import PANELS

PLAYER_HEIGHT = 25.65
HEAD_X_SCALE = 1.03
HEAD_Z_SCALE = 1.18


def geometry():
    verts, faces, uvs, groups, smooth = [], [], [], [], []

    def vertex(point, weights):
        verts.append(tuple(point))
        groups.append(weights if isinstance(weights, dict) else {weights: 1.})
        return len(verts)-1

    def uv(panel, u, v):
        x0, y0, x1, y1 = PANELS[panel]
        return ((x0+1+max(0., min(1., u))*(x1-x0-2))/256,
                1-(y0+1+max(0., min(1., v))*(y1-y0-2))/256)

    def face(indices, surface, softened=False, coords=None):
        faces.append(indices)
        if coords is None:
            normal = (Vector(verts[indices[1]])-Vector(verts[indices[0]])).cross(
                Vector(verts[indices[2]])-Vector(verts[indices[0]]))
            if surface == 'jacket':
                surface = 'jacket_front' if normal.y < -.1 else 'jacket_back'
            coords = []
            for index in indices:
                x, y, z = verts[index]
                if surface in ('jacket_front', 'jacket_back'):
                    u, v = .5+x/6.8, (24.5-z)/11.2
                    if surface == 'jacket_back': u = 1-u
                elif surface == 'face': u, v = .5+x/2.65, (27.8-z)/3.3
                elif surface == 'side_face':
                    u = (math.degrees(math.atan2(abs(x), -y))-54)/126
                    v = (27.8-z)/3.3
                elif surface == 'tee': u, v = .5+x/2.3, (24.-z)/10.65
                elif surface == 'hair': u, v = .5+x/2.8, (28-z)/2.2
                elif surface == 'skin': u, v = .5+y/2.5, (27-z)/3.
                elif surface == 'pants': u, v = .5+y/2.9, (14.7-z)/13.4
                elif surface == 'shoe': u, v = .5+x/2.1, (y+2.2)/3.3
                elif surface == 'sole': u, v = .5+y/3.6, (z-.1)/.45
                else: u, v = .5+x/6.8, (24.5-z)/10.
                coords.append(uv(surface, u, v))
        uvs.append(coords)
        smooth.append(softened)

    def bridge(a, b, surface, softened=True, v0=None, v1=None):
        for k in range(len(a)):
            j = (k+1)%len(a)
            coords = None
            if v0 is not None:
                coords = [uv(surface, k/len(a), v0), uv(surface, (k+1)/len(a), v0),
                          uv(surface, (k+1)/len(a), v1), uv(surface, k/len(a), v1)]
            face([a[k], a[j], b[j], b[k]], surface, softened, coords)

    def section(rings, surface, sides=12, softened=True, cap_top=True):
        result = []
        for cx, cy, z, rx, ry, weights in rings:
            result.append([vertex((cx+rx*math.cos(k*math.tau/sides),
                                   cy+ry*math.sin(k*math.tau/sides), z), weights)
                           for k in range(sides)])
        for a, b in zip(result, result[1:]): bridge(a, b, surface, softened)
        face(list(reversed(result[0])), surface)
        if cap_top: face(result[-1], surface)
        return result

    # Torso: broad chest, tapered waist, soft hem. Opening topology is shared
    # by the shoulder and sleeve, so pumping arms cannot reveal cylinder caps.
    torso = []
    dimensions = ((13.35, 2.20, 1.30), (14.3, 2.32, 1.34),
                  (16.0, 2.45, 1.36), (18.6, 2.78, 1.47),
                  (20.4, 3.05, 1.52), (22.1, 3.06, 1.48),
                  (23.3, 2.95, 1.30), (24.0, 1.17, .87))
    for row, (z, rx, ry) in enumerate(dimensions):
        weights = {'root': 1.} if row == 0 else {'root': .65, 'spine': .35} if row == 1 else {'root': .2, 'spine': .8} if row == 2 else {'spine': 1.}
        torso.append([vertex((rx*math.cos(k*math.tau/16), ry*math.sin(k*math.tau/16), z), weights) for k in range(16)])
    for row in range(len(torso)-1):
        for k in range(16):
            if row in (4, 5) and k in (14, 15, 0, 1, 6, 7, 8, 9): continue
            j = (k+1)%16
            # The tee shares the torso's boundary vertices with the jacket.
            # Its fabric cannot intersect an overlapping chest shell.
            # Keep the tee above the waistband; the jacket's lower front
            # closes over it rather than exposing white polygons at the crotch.
            surface = 'tee' if row>=1 and k in (11, 12) else 'jacket'
            face([torso[row][k], torso[row][j], torso[row+1][j], torso[row+1][k]], surface, True)
    face(list(reversed(torso[0])), 'jacket')
    face(torso[-1], 'jacket')

    for sign, suffix, start in ((1, 'R', 14), (-1, 'L', 6)):
        arm, forearm, hand = ('arm.'+suffix, 'forearm.'+suffix, 'hand.'+suffix)
        arc = [(start+k)%16 for k in range(5)]
        opening = ([torso[4][k] for k in arc]+[torso[5][arc[-1]], torso[6][arc[-1]]]
                   +[torso[6][k] for k in reversed(arc[:-1])]+[torso[5][arc[0]]])
        for index in opening:
            influence = .22 if verts[index][2]>22 else .08
            groups[index] = {'spine': 1-influence, arm: influence}
        angles = (225, 247.5, 270, 292.5, 315, 0, 45, 67.5, 90, 112.5, 135, 180)
        previous = opening
        rings = [
            (3.35, 22.4, .91, 1.02, 60, {'spine': .28, arm: .72}, 'sleeve'),
            (3.52, 21.8, .93, 1.00, 85, {arm: 1.}, 'sleeve'),
            (3.53, 20.7, .91, .93, 90, {arm: 1.}, 'sleeve'),
            (3.5, 19.0, .79, .85, 90, {arm: 1.}, 'sleeve'),
            (3.5, 18.15, .73, .78, 90, {arm: .90, forearm: .10}, 'sleeve'),
            (3.5, 17.7, .75, .77, 90, {arm: .5, forearm: .5}, 'sleeve'),
            (3.5, 17.25, .73, .75, 90, {arm: .12, forearm: .88}, 'sleeve'),
            (3.5, 16.2, .72, .75, 90, {forearm: 1.}, 'sleeve'),
            (3.5, 14.4, .57, .59, 90, {forearm: 1.}, 'sleeve'),
            (3.5, 13.65, .48, .49, 90, {forearm: .95, hand: .05}, 'sleeve'),
            (3.5, 13.4, .49, .50, 90, {forearm: .7, hand: .3}, 'sleeve'),
            (3.5, 13.27, .40, .38, 90, {forearm: .4, hand: .6}, 'skin'),
            (3.5, 12.9, .54, .36, 90, {hand: 1.}, 'skin'),
            (3.5, 12.4, .54, .33, 90, {hand: 1.}, 'skin'),
            (3.5, 12.05, .46, .31, 90, {hand: 1.}, 'skin'),
            (3.5, 11.8, .31, .25, 90, {hand: 1.}, 'skin')]
        for cx, z, rx, ry, tilt, weights, surface in rings:
            tilt = math.radians(tilt)
            current = []
            for k, degrees in enumerate(angles):
                a = math.radians(degrees)
                radius = rx+(.23 if k in (1, 2, 3) and z==12.9 else .12 if k==2 and z==12.4 else 0.)
                current.append(vertex((sign*(cx+radius*math.sin(a)*math.sin(tilt)),
                                       sign*ry*math.cos(a), z+radius*math.sin(a)*math.cos(tilt)), weights))
            # Full length sleeve UV: cuffs remain at the wrist, not at elbows.
            if surface == 'sleeve':
                bridge(previous, current, surface, True,
                       max(0, (22.4-(verts[previous[0]][2]))/9.1), (22.4-z)/9.1)
            else: bridge(previous, current, surface, True)
            previous = current
        face(previous, 'skin', True)

    # A neck is visible inside the crew collar, joining the adult-sized head.
    neck = section([(0, .03, 23.55, .86, .74, 'spine'),
                    (0, .03, 24.3, .84, .73, {'spine': .4, 'head': .6}),
                    (0, .03, 24.63, .82, .72, {'spine': .05, 'head': .95})],
                   'skin', 20, cap_top=False)
    neck_vertices = {index for ring in neck for index in ring}

    # Sculpted chin, jaw, cheek, eye socket, bridge, forehead and skull.
    head = []
    head_rings = ((24.45, .64, .82, -.15), (24.75, .88, .85, -.12),
                  (25.0, 1.10, .92, -.08), (25.28, 1.18, 1.0, -.05),
                  (25.62, 1.27, 1.02, .00), (25.92, 1.28, 1.04, .00),
                  (26.18, 1.23, 1.04, .00), (26.45, 1.18, 1.03, .02),
                  (26.75, 1.19, 1.05, .03), (27.08, 1.18, 1.06, .04),
                  (27.43, 1.08, 1.0, .05), (27.70, .78, .74, .04))
    def back_depth(z, angle):
        # Keep the successful front likeness, but give the cranium enough
        # depth behind the ears instead of a flattened front-photo silhouette.
        depth = .15+.23*min(1., max(0., (z-24.75)/.85))
        return depth*max(0., -math.cos(angle))
    for z, rx, ry, cy in head_rings:
        ring = []
        for k in range(20):
            a = k*math.tau/20
            x, y = rx*math.sin(a), cy-ry*math.cos(a)+back_depth(z, a)
            if math.cos(a) > .8:
                # A narrower nose bridge and tip, small eye-socket recess.
                if k == 0:
                    y -= {25.0: .025, 25.28: .10, 25.62: .32, 25.92: .25,
                          26.18: .14, 26.45: .035}.get(z, 0.)
                elif k in (1, 19) and z in (25.62,25.92): y -= .065
                elif k in (1, 19) and z in (26.18, 26.45): y += .045
            # The mandible rises toward the ear/nape. Horizontal lower rings
            # otherwise create a hanging bowl behind a sharply receding chin.
            rear = max(0., (1-math.cos(a)-(1-math.cos(math.radians(54)))) /
                       (1+math.cos(math.radians(54))))
            jaw_lift = .72*max(0., (25.62-z)/(25.62-24.45))*rear
            ring.append(vertex((x, y, z+jaw_lift), 'head'))
        head.append(ring)
    for row in range(len(head)-1):
        for k in range(20):
            j = (k+1)%20
            ids = [head[row][k], head[row][j], head[row+1][j], head[row+1][k]]
            surface = 'face' if math.cos((k+.5)*math.tau/20) > .5 else 'side_face'
            coords = None
            if surface == 'side_face':
                angles = (k*math.tau/20, j*math.tau/20,
                          j*math.tau/20, k*math.tau/20)
                coords = [uv(surface, (math.degrees(min(a, math.tau-a))-54)/126,
                             (27.8-verts[index][2])/3.3)
                          for index, a in zip(ids, angles)]
            face(ids, surface, True, coords)
    # A shared neck-to-mandible surface avoids a visible cap/intersection seam
    # at the nape. Align the neck's circular indexing with the front-first jaw.
    bridge([neck[-1][(k+15)%20] for k in range(20)], head[0], 'skin', True)
    face(head[-1], 'hair')

    for sign in (-1, 1):
        section([(sign*1.25, .16, 25.72, .08, .15, 'head'),
                 (sign*1.29, .17, 25.88, .13, .19, 'head'),
                 (sign*1.28, .19, 26.16, .14, .20, 'head'),
                 (sign*1.25, .20, 26.34, .07, .15, 'head')], 'side_face', 8, True)

    # Close-cropped sides and a slightly asymmetric, swept top silhouette.
    hair = []
    def scalp_radius(z):
        if z>=head_rings[-1][0]:
            t=max(0.,min(1.,(z-head_rings[-1][0])/(28-head_rings[-1][0])))
            radius=math.sqrt(max(0.,1-t*t))
            return .78*radius+.045,.74*radius+.045,.04
        for a,b in zip(head_rings,head_rings[1:]):
            if a[0]<=z<=b[0]:
                t=(z-a[0])/(b[0]-a[0])
                return a[1]+(b[1]-a[1])*t+.065,a[2]+(b[2]-a[2])*t+.065,a[3]+(b[3]-a[3])*t
        return 1.30,1.13,.03
    def scalp_point(z,k):
        a=k*math.tau/20
        if z>=head_rings[-1][0]:
            rx,ry,cy=scalp_radius(z)
            return Vector((rx*math.sin(a),cy-ry*math.cos(a)+back_depth(z,a),z))
        # The lower jaw rises toward the nape. Sample its actual displaced
        # rings so a lower back hairline follows the skull rather than jutting
        # out from the old, flat ring heights.
        for lower,upper in zip(head,head[1:]):
            p,q=Vector(verts[lower[k]]),Vector(verts[upper[k]])
            if p.z<=z<=q.z:return p.lerp(q,(z-p.z)/(q.z-p.z))
        raise ValueError('Hairline lies below the skull surface')
    for row in range(9):
        t = row/8
        ring = []
        for k in range(20):
            a = k*math.tau/20
            front = max(0., math.cos(a))
            bottom = 25.90+1.06*front-.70*max(0.,-math.cos(a))+.10*math.sin(a)+.28*math.sin(a)*front*front
            z = bottom+(28-bottom)*t
            point=scalp_point(z,k)
            fullness=.07*math.sin(t*math.pi)
            padding=(.065+.065*max(0.,-math.cos(a))*(1-t)**2
                     if z<head_rings[-1][0] else 0.)
            x = point.x+(padding+fullness)*math.sin(a)-.045*math.sin(t*math.pi)
            y = point.y-(padding+fullness)*math.cos(a)
            ring.append(vertex((x, y, z), 'head'))
        hair.append(ring)
    for a, b in zip(hair, hair[1:]): bridge(a, b, 'hair', True)
    face(hair[-1],'hair',True)

    # Shoes retain the established heel/toe contacts and atlas.
    for sign, suffix in ((-1, 'L'), (1, 'R')):
        x = sign*1.30
        foot = 'foot.'+suffix
        # Shoes with a beveled leather upper, low heel and dark outsole.
        rings = []
        for z, rx, ry, cy in ((.10, .85, 1.65, -.55),
                              (.32, .89, 1.65, -.55),
                              (.47, .87, 1.61, -.54),
                              (.95, .80, 1.40, -.40),
                              (1.32, .66, .86, -.06)):
            current = [vertex((x+rx*math.cos(k*math.tau/12), cy+ry*math.sin(k*math.tau/12), z), foot) for k in range(12)]
            if rings:
                # Local shoe UV makes both shoes share identical leather detail.
                surface = 'sole' if z<=.47 else 'shoe'
                coords = []
                for k in range(12):
                    j = (k+1)%12
                    ids = [rings[-1][k], rings[-1][j], current[j], current[k]]
                    coords = [uv(surface, .5+(verts[i][0]-x)/1.9, (verts[i][1]+2.2)/3.3) for i in ids]
                    face(ids, surface, True, coords)
            rings.append(current)
        face(list(reversed(rings[0])), 'sole')
        face(rings[-1], 'shoe', True,
             [uv('shoe', .5+(verts[i][0]-x)/1.9, (verts[i][1]+2.2)/3.3) for i in rings[-1]])

    # Modeled collar leaves cast a recognisable fold in the low-res silhouette.
    for sign in (-1, 1):
        points = [(sign*.69, -.79, 24.05), (sign*1.63, -1.08, 23.40),
                  (sign*1.25, -1.49, 22.47), (sign*.56, -1.30, 23.54)]
        ids = [vertex(point, 'spine') for point in points]
        if sign<0: ids.reverse()
        face(ids, 'collar', False, [uv('collar', u, v) for u, v in ((.08, .05), (.9, .1), (.8, .9), (.05, .8))])
        back = [vertex((x, y+.08, z), 'spine') for x, y, z in points]
        back_ids = list(reversed(back if sign>0 else list(reversed(back))))
        face(back_ids, 'collar', False,
             [uv('collar', .12, .75) for _ in back_ids])
        for k in range(4):
            j = (k+1)%4
            # The narrow thickness receives fabric instead of exposing a plane.
            a = ids[k]; b = ids[j]
            # Spatial pairing independent of left-side winding.
            ai = min(back, key=lambda i: (Vector(verts[i])-Vector(verts[a])).length)
            bi = min(back, key=lambda i: (Vector(verts[i])-Vector(verts[b])).length)
            face([a, ai, bi, b], 'collar', False,
                 [uv('collar', .12, .75)]*4)

    # Retain the UV construction/topology above while changing the silhouette.
    # Piecewise anatomical maps shorten each limb at its actual joint, so the
    # mesh, rest skeleton and fixed-length animation targets remain aligned.
    def remap(z,points):
        for (a,b),(c,d) in zip(points,points[1:]):
            if z<=c:return b+(z-a)*(d-b)/(c-a)
        a,b=points[-2];c,d=points[-1]
        return b+(z-a)*(d-b)/(c-a)
    torso_map=((13.35,11.90),(14.,12.6),(24.3,20.9))
    leg_map=((1.,1.),(7.5,6.8),(14.,12.6))
    arm_map=((11.8,10.397),(13.3,11.897),(17.7,15.355),(22.8,19.45))
    for i,((x,y,z),weights) in enumerate(zip(verts,groups)):
        if i in neck_vertices:
            # Keep a substantial neck beneath the jaw when slimming the chest.
            # Its radii are anatomical dimensions, independent of jacket taper.
            verts[i]=(x,y,remap(z,torso_map))
        elif 'head' in weights and 'spine' not in weights:
            # Narrow the full skull/ears/hair around the preserved portrait UVs.
            # Move the preserved face down with the shorter upper torso.
            verts[i]=(x*HEAD_X_SCALE,y*1.09,PLAYER_HEIGHT-(28-z)*HEAD_Z_SCALE)
        elif any(name.startswith(('arm.','forearm.','hand.')) for name in weights) and 'spine' not in weights:
            sign=1 if x>0 else -1
            verts[i]=(sign*2.6+(x-sign*3.5)*.78,y*.90,remap(z,arm_map))
        elif len(weights)==1 and next(iter(weights)).startswith('foot.'):
            # Shoe/sole dimensions define the heel-toe contact solve; preserve
            # them rather than moving the sole when the shins get shorter.
            verts[i]=(x,y,z)
        elif any(name.startswith(('thigh.','shin.','foot.')) for name in weights) or z<14.7:
            verts[i]=(x,y,remap(z,leg_map))
        else:
            # Preserve the waist/seat, taper the oversized deltoids and chest.
            taper=min(1.,max(0.,(z-14)/6.))
            width=1.02-.23*taper
            verts[i]=(x*width,y*(1-.06*taper),remap(z,torso_map))
    # The trousers are one connected surface: shared waist, seat and saddle
    # branch into the two legs. This removes the old three capped cylinders.
    # These coordinates are already in the final skeleton's rest dimensions.
    waist=[]
    rows=((13.10,1.98,1.08),(12.60,2.02,1.14),(12.05,2.05,1.19),(11.60,2.10,1.22))
    for row,(z,rx,ry) in enumerate(rows):
        ring=[]
        for k in range(24):
            a=k*math.tau/24
            x=rx*math.sin(a);y=-ry*math.cos(a)
            # The lower front/back seam rises gently into the hip crease.
            zz=z-.30*abs(math.cos(a)) if row==3 else z
            if row<2:w={'root':1.}
            else:
                influence=(.12 if row==2 else .38)*abs(math.sin(a))
                w={'root':1-influence,('thigh.R' if x>=0 else 'thigh.L'):influence}
            ring.append(vertex((x,y,zz),w))
        waist.append(ring)
        if row:bridge(ring,waist[-2],'pants',True)
    face(waist[0],'pants',True)
    bottom=waist[-1]
    # Shared crotch seam, curving under the seat instead of a horizontal cap.
    seam=[]
    for k in range(1,6):
        t=k/6
        y=1.22*(1-2*t)
        z=11.30-.40*math.sin(math.pi*t)
        seam.append(vertex((0,y,z),{'root':.78,'thigh.L':.11,'thigh.R':.11}))
    leg_rows=((10.30,1.14,1.16),(9.15,1.07,1.10),(8.10,1.00,1.02),
              (7.35,.96,.94),(6.85,.94,.91),(6.35,.91,.89),
              (5.30,.91,.89),(4.20,.87,.85),(3.10,.78,.76),
              (2.05,.72,.70),(1.35,.73,.71))
    for sign,suffix in ((1,'R'),(-1,'L')):
        outer=([bottom[k] for k in range(13)] if sign==1 else
               [bottom[k%24] for k in range(12,25)])
        current=outer+(seam if sign==1 else list(reversed(seam)))
        for z,rx,ry in leg_rows:
            if z>=8.1:w={'thigh.'+suffix:1.}
            elif z>=7.35:w={'thigh.'+suffix:.92,'shin.'+suffix:.08}
            elif z>=6.85:w={'thigh.'+suffix:.55,'shin.'+suffix:.45}
            elif z>=6.35:w={'thigh.'+suffix:.12,'shin.'+suffix:.88}
            elif z>1.4:w={'shin.'+suffix:1.}
            else:w={'shin.'+suffix:.88,'foot.'+suffix:.12}
            following=[]
            for k in range(18):
                a=(math.pi*k/12 if k<=12 else math.pi+math.pi*(k-12)/6)
                # Soft cloth shaping; a rounded outer thigh, quiet knee folds.
                fold=.018*math.sin(3.2*z+2*a)*math.exp(-((z-6.8)/1.3)**2)
                x=sign*(1.30+(rx+fold)*math.sin(a))
                y=-sign*(ry+fold*.8)*math.cos(a)
                following.append(vertex((x,y,z),w))
            bridge(following,current,'pants',True)
            current=following
        # Hem has a narrow inward facing lip around the shoe upper.
        lip=[]
        for index in current:
            x,y,z=verts[index]
            lip.append(vertex((sign*1.30+(x-sign*1.30)*.94,y*.94,z+.035),groups[index]))
        bridge(lip,current,'pants',True)
    # A modest rounded thumb separates the hand silhouette from a mitten.
    for sign,suffix in ((1,'R'),(-1,'L')):
        before=len(faces)
        section([(sign*2.23,-.02,11.027,.11,.14,'hand.'+suffix),
                 (sign*2.16,-.10,11.217,.16,.18,'hand.'+suffix),
                 (sign*2.28,-.08,11.517,.15,.18,'hand.'+suffix)],'skin',8,True)
        for i in range(before,len(faces)):
            uvs[i]=[uv('skin',.55,.56) for _ in faces[i]]
    return verts, faces, uvs, groups, smooth
