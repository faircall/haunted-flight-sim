"""Blender-independent ground-floor contract shared by house mesh and navigation.

Coordinates are unwarped house-local X/Z. The district applies the same small
ground shear and yaw as the geometry kit. Door ranges describe clear apertures;
porch posts sit on their piers rather than on their approach axes.
"""

def house_ground_plan(spec):
    w=float(spec['width']);d=float(spec['depth'])
    front=-d/2;back=d/2
    porch=float(spec.get('porch',min(1.15,d*.18)))
    wall=front+porch
    variant=spec.get('variant','plaster')
    if spec.get('door_ranges'):
        doors=[tuple(map(float,v)) for v in spec['door_ranges']]
    elif variant in ('timber_gallery','shopfront','arcade'):
        cuts=(-w/2,-w/2+w*.36,-w/2+w*.71,w/2)
        doors=[(a+.16,b-.16) for a,b in zip(cuts,cuts[1:])]
    else:
        width=min(w*.42,max(1.35,w*.27))
        center=-w*.13 if variant=='corner' else w*.18
        doors=[(center-width/2,center+width/2)]
    # A folded leaf can make an apparently wide aperture impassable. Accessible
    # houses have missing leaves; all clear widths here are real free widths.
    posts=[(-w/2+.14,front+.12,.18),(w/2-.14,front+.12,.18)]
    if len(doors)>1:
        posts.extend(((a[1]+b[0])/2,front+.12,.16) for a,b in zip(doors,doors[1:]))
    rear_access=bool(spec.get('rear_access',False))
    rear_doors=[];rear_landing=None
    if rear_access:
        if spec.get('rear_door_ranges'):
            rear_doors=[tuple(map(float,v)) for v in spec['rear_door_ranges']]
        else:
            rear_width=float(spec.get('rear_door_width',min(1.80,max(1.35,w*.22))))
            rear_x=float(spec.get('rear_door_x',0.))
            rear_doors=[(rear_x-rear_width/2,rear_x+rear_width/2)]
        x0=min(v[0] for v in rear_doors);x1=max(v[1] for v in rear_doors)
        landing_width=max(float(spec.get('rear_landing_width',2.0)),x1-x0+.50)
        landing_center=(x0+x1)/2
        rear_landing=(landing_center-landing_width/2,back-.28,
                      landing_center+landing_width/2,
                      back+float(spec.get('rear_landing_depth',1.15)))
    return dict(front=front,frontwall=wall,porch=porch,door_ranges=doors,
                posts=posts,room_bounds=(-w/2+.28,wall+.25,w/2-.28,back-.28),
                porch_bounds=(-w/2+.28,front,w/2-.28,wall),
                ground_y=float(spec.get('base_y',.325)),
                wall_thickness=.25,threshold=.025,
                rear_access=rear_access,rearwall=back,
                rear_door_ranges=rear_doors,rear_landing_bounds=rear_landing)
