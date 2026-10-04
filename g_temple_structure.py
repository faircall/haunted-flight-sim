"""Live-3D temple footprint and stair heights; the original 2D scene is retained."""
from copy import deepcopy
from dataclasses import dataclass
import math

TEMPLE_HEIGHT=24.
BRIDGE_HEIGHT=16.
TEMPLE_BOUNDS=(400.,176.,560.,280.)


@dataclass(frozen=True)
class Stairs:
    name:str
    bounds:tuple
    axis:str
    bottom:float
    top:float
    count:int

    def contains(self,x,z):
        x0,z0,x1,z1=self.bounds
        return x0<=x<x1 and z0<=z<z1

    def treads(self):
        x0,z0,x1,z1=self.bounds
        for i in range(self.count):
            if self.axis=='x':
                a=x0+(x1-x0)*i/self.count;b=x0+(x1-x0)*(i+1)/self.count
                bounds=(a,z0,b,z1)
            else:
                a=z1-(z1-z0)*(i+1)/self.count;b=z1-(z1-z0)*i/self.count
                bounds=(x0,a,x1,b)
            yield bounds,self.bottom+(self.top-self.bottom)*(i+1)/self.count

    def height(self,x,z):
        x0,z0,x1,z1=self.bounds
        t=(x-x0)/(x1-x0) if self.axis=='x' else (z1-z)/(z1-z0)
        return self.bottom+(self.top-self.bottom)*min(self.count,max(1,math.floor(t*self.count)+1))/self.count


STAIRS=(Stairs('shore',(140.,320.,176.,352.),'x',0.,BRIDGE_HEIGHT,6),
        Stairs('threshold',(464.,280.,496.,296.),'-z',BRIDGE_HEIGHT,TEMPLE_HEIGHT,4))


def prepare(arena):
    """Trim the forecourt/skirt and give the building its own higher foundation."""
    tm=deepcopy(arena['tile_map']);entities=deepcopy(arena['entities'])
    for index,tile in enumerate(tm['tiles']):
        if tile.get('surface_material') not in ('wood','wall'):continue
        x,y=index%tm['map_width'],index//tm['map_width']
        temple=25<=x<35 and 11<=y<17
        bridge=(11<=x<31 and 20<=y<22) or (29<=x<31 and 17<=y<20)
        if temple:
            tile.update(surface_elevation=TEMPLE_HEIGHT,structure='temple')
        elif bridge:
            tile.update(surface_elevation=BRIDGE_HEIGHT,structure='bridge',surface_axis='y' if y<20 else 'x')
        else:
            tile.clear()
            tile.update(index=0,water=True,lake_bed=True,force_collidable=True,rain_exposure=1.)
    tm['temple3d_layout']=True
    tm['surface_revision']=tm.get('surface_revision',0)+1
    props=entities['lake_props']
    for name in list(props):
        prop=props[name]
        if prop['kind']=='rail' or (prop['kind']=='pile' and not name.startswith('lantern-post:')):
            del props[name]
    def rail(name,x,z,angle=0):
        props[name]=dict(kind='rail',asset='baked:rail32',position=dict(x=x,y=z),rotation_y=angle,
                         geometry_offset=(0.,0.,0.),base_height=BRIDGE_HEIGHT)
    # Physical rail positions now sit on the actual deck edges, including the
    # perpendicular connector. Leave the elbow and doorway open to walking.
    for x in range(192,481,32):
        rail(f'bridge-front:{x}',x,350.)
        if x<464:rail(f'bridge-back:{x}',x,322.)
    rail('connector-left',466.,304.,90.)
    rail('connector-right',494.,304.,90.)
    rail('bridge-end',494.,336.,90.)
    # Former forecourt objects would float over the removed platform. Move them
    # onto the building or existing bridge; keep the doorway unobstructed.
    placements={'lantern-post:2':(272.,348.),'lantern:2':(272.,348.),
                'lantern-post:3':(446.,348.),'lantern:3':(446.,348.),
                'bowl:approach':(222.,344.),'bowl:crossing':(334.,344.),
                'bowl:landing':(422.,258.),'bowl:landing-r':(538.,258.)}
    for name,prop in props.items():
        if name in placements:prop['position']=dict(zip(('x','y'),placements[name]))
        p=prop['position']
        prop['base_height']=0. if prop['kind']=='lily' else TEMPLE_HEIGHT if 400<=p['x']<=560 and 176<=p['y']<=280 else BRIDGE_HEIGHT
        if name.startswith('bowl:'):
            emitter=entities['emitters'][name[5:]]
            emitter['position']=dict(p)
            emitter['base_height']=prop['base_height']
    for facade in entities['facades'].values():facade['base_height']=TEMPLE_HEIGHT
    return arena.set('tile_map',tm).set('entities',entities)


def floor_height(tm,x,z):
    if tm.get('temple3d_layout'):
        for stairs in STAIRS:
            if stairs.contains(x,z):return stairs.height(x,z)
        if 400<=x<560 and 272<=z<280:return TEMPLE_HEIGHT
    tx,ty=math.floor(x/16),math.floor(z/16)
    if 0<=tx<tm['map_width'] and 0<=ty<tm['map_height']:
        return float(tm['tiles'][ty*tm['map_width']+tx].get('surface_elevation',0.))
    return 0.
