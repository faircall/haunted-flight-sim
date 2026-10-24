"""Compact native controls and spatial guides for authored fog volumes."""
from copy import deepcopy
import math
import pyray as pr

from temple_cinematics_editor import contains, label

INK=pr.Color(221,232,229,255); MUTED=pr.Color(133,160,163,255)
ACCENT=pr.Color(228,183,113,255); BLUE=pr.Color(116,177,237,255)
GREEN=pr.Color(61,119,104,255); BG=pr.Color(13,20,23,215)
TIME_KEYS=('fade_in_start','fade_in_end','reveal_start','reveal_end')


class VolumePanel:
    def __init__(self,editor):
        self.editor=editor;self.page='shape';self.list_page=0

    @property
    def state(self):return self.editor.state

    def controls(self):
        e=self.editor;s=self.state;a=e.layout();x=a['right']+14
        settings=s.volume_settings;region=s.volume
        buttons=[('vol:enabled','Volumes: '+('ON' if settings['enabled'] else 'OFF'),(x,177,131,29),settings['enabled']),
                 ('vol:quality','Quality: '+settings['quality'].title(),(x+141,177,131,29),False)]
        for i,(key,title) in enumerate((('quads','Quads only'),('volume','Volumes only'),('hybrid','Hybrid'))):
            active=(key=='quads' and not settings['enabled'] or key=='volume' and settings['enabled'] and settings['particle_mix']==0 or key=='hybrid' and settings['enabled'] and settings['particle_mix']>0)
            buttons.append(('vol:preset:'+key,title,(x+i*94,215,86,29),active))
        fields=[(('vol_global','mix'),(x,267,131,30)),(('vol_global','particle_mix'),(x+141,267,131,30))]
        for i,(key,title) in enumerate((('shape','Shape'),('flow','Flow'),('timing','Timing'))):
            buttons.append(('vol:page:'+key,title,(x+i*94,312,86,28),self.page==key))
        buttons.extend([('vol:add:box','+ Box volume',(10,111,216,29),False),
                        ('vol:add:ellipsoid','+ Ellipsoid volume',(10,147,216,29),False),
                        ('vol:fit','+ Fit selected building',(10,183,216,29),False)])
        regions=list(s.volume_regions.items());pages=max(1,math.ceil(len(regions)/8))
        self.list_page=max(0,min(pages-1,self.list_page))
        for i,(identity,item) in enumerate(regions[self.list_page*8:self.list_page*8+8]):
            buttons.append(('vol:select:'+identity,('' if item['enabled'] else '[off] ')+item['label'],(10,277+i*32,216,29),identity==s.volume_id))
        buttons.extend([('vol:prev','<',(10,540,42,25),False),('vol:next','>',(184,540,42,25),False)])
        if region:
            fields.append((('vol','label'),(x,354,157,25)))
            buttons.extend([('vol:duplicate','Duplicate',(10,578,103,29),False),('vol:remove','Remove',(123,578,103,29),False),
                            ('vol:frame','Frame selected volume',(10,615,216,29),False),
                            ('vol:region_enabled','Region: '+('ON' if region['enabled'] else 'OFF'),(x+165,354,107,25),region['enabled'])])
            if self.page=='shape':
                for i,shape in enumerate(('box','ellipsoid')):
                    buttons.append(('vol:shape:'+shape,shape.title(),(x+i*141,392,131,28),region['shape']==shape))
                fields.extend([(('vol',prop,i),(x+i*94,y,86,30)) for prop,y in (('center',447),('half_extents',510)) for i in range(3)])
                fields.extend([(('vol','yaw'),(x+140,557,132,30)),(('vol','hollow'),(x+140,600,132,30))])
            elif self.page=='flow':
                fields.extend([(('vol',prop),(x+140,y,132,30)) for prop,y in (('density',393),('edge',435),('noise_size',477),('turbulence',519))])
                fields.extend([(('vol','wind',i),(x+i*94,587,86,30)) for i in range(3)])
            else:
                fields.extend([(('vol',prop),(x+i*141,y,131,30)) for props,y in ((TIME_KEYS[:2],417),(TIME_KEYS[2:],487)) for i,prop in enumerate(props)])
                fields.extend([(('vol','retreat',i),(x+i*94,567,86,30)) for i in range(3)])
        return buttons,fields

    def field_value(self,path):
        source=self.state.volume_settings if path[0]=='vol_global' else self.state.volume
        value=source[path[1]]
        return value[path[2]] if len(path)>2 else value

    def set_field(self,path,value):
        if path[0]=='vol_global':self.state.set_volume_global(path[1],value)
        else:self.state.set_volume(path[1],value,path[2] if len(path)>2 else None)

    def action(self,name):
        e=self.editor;s=self.state;key=name[4:]
        if key=='enabled':s.set_volume_global('enabled',not s.volume_settings['enabled'])
        elif key=='quality':
            values=('draft','balanced','high');s.set_volume_global('quality',values[(values.index(s.volume_settings['quality'])+1)%len(values)])
        elif key.startswith('preset:'):
            preset=key[7:]
            def apply():
                settings=deepcopy(s.volume_settings)
                settings.update(enabled=preset!='quads',mix=1.,particle_mix=0. if preset=='volume' else 1.)
                s.document['volumes']=settings
            s.change(apply)
        elif key.startswith('page:'):self.page=key[5:]
        elif key.startswith('add:'):
            s.add_volume(shape=key[4:]);self.show_selected()
        elif key=='fit':
            if s.target.kind not in ('house','bridge'):
                e.status='Select a building in the preview first, then fit a volume.';return
            s.add_volume(target_id=s.target_id);self.show_selected()
        elif key.startswith('select:'):s.select_volume(key[7:])
        elif key in ('prev','next'):
            self.list_page=max(0,min(max(0,math.ceil(len(s.volume_regions)/8)-1),self.list_page+(1 if key=='next' else -1)))
        elif key=='duplicate':s.duplicate_volume();self.show_selected()
        elif key=='remove':s.delete_volume()
        elif key=='region_enabled':s.set_volume('enabled',not s.volume['enabled'])
        elif key.startswith('shape:'):s.set_volume('shape',key[6:])
        elif key=='frame':
            region=s.volume;centre=region['center'];size=max(region['half_extents'])
            e.inspection=dict(eye=[centre[0]+size*1.7,centre[1]+size*1.3,centre[2]+size*2.2],target=list(centre),fov=58.)
            s.playing=False
        e.status='Volumetric preview / '+('enabled' if s.volume_settings['enabled'] else 'disabled')+' / changes remain editable until Save.'

    def show_selected(self):
        identities=list(self.state.volume_regions)
        if self.state.volume_id in identities:self.list_page=identities.index(self.state.volume_id)//8

    def time_handles(self):
        if not self.state.volume:return []
        e=self.editor;y=e.layout()['timeline'][1]
        return [(key,(e.x_at(self.state.volume[key])-8,y+36+(i//2)*30-5,16,23)) for i,key in enumerate(TIME_KEYS)]

    def clamp_time(self,key,value):
        region=self.state.volume;index=TIME_KEYS.index(key)
        low=0. if index==0 else region[TIME_KEYS[index-1]]+(.1 if index in (1,3) else 0.)
        if key=='reveal_start':low=max(low,self.state.document['cues']['blend_end'])
        high=self.state.duration if index==3 else region[TIME_KEYS[index+1]]-(.1 if index in (0,2) else 0.)
        return max(low,min(high,value))

    def draw_labels(self):
        e=self.editor;s=self.state;a=e.layout();x=a['right']+14;region=s.volume
        def text(value,px,py,size=11,colour=MUTED):pr.draw_text(value,int(px),int(py),size,colour)
        text('Select building in preview to fit.',13,223)
        text(label(s.target_id,212,11),13,240,11,ACCENT)
        text('AUTHORED VOLUMES',13,260,11,INK)
        pages=max(1,math.ceil(len(s.volume_regions)/8))
        text(f'{self.list_page+1} / {pages}  ({len(s.volume_regions)})',64,548)
        text('Volume amount',x,250);text('Quad amount',x+141,250)
        if not region:
            text('Create a volume to begin.',x,365,13,INK)
            text('Boxes fill rooms, lanes and water.',x,395)
            text('Ellipsoids make softer cloud banks.',x,415)
            text('Fit follows the selected building.',x,435)
            return
        if self.page=='shape':
            text('CENTRE / world metres',x,429)
            text('HALF-SIZE / metres from centre',x,491)
            text('Rotation / degrees',x,568,12,INK);text('Hollow core / 0 to .95',x,611,12,INK)
            text('Drag XYZ handles to move; RMB to inspect.',x,650,10)
        elif self.page=='flow':
            for title,y in (('Density',404),('Soft edge / fraction',446),('Noise size / metres',488),('Turbulence',530)):
                text(title,x,y,12,INK)
            text('WIND / metres per second',x,569)
            text('Noise rolls inside the volume bounds.',x,640)
        else:
            text('BUILD / seconds',x,391,12,INK)
            text('Starts',x,404,10);text('Full density',x+141,404,10)
            text('CLEAR / seconds',x,461,12,INK)
            text('Starts',x,474,10);text('Gone',x+141,474,10)
            text('RETREAT / total displacement, metres',x,548)
            text('Drag the two tracks below to retime.',x,616)
            text('Retreat moves the volume as it clears.',x,635)

    def draw_timeline(self):
        if not self.state.volume:return
        e=self.editor;region=self.state.volume;ty=e.layout()['timeline'][1]
        for i,(start,end,title) in enumerate(((*TIME_KEYS[:2],'BUILD'),(*TIME_KEYS[2:],'CLEAR'))):
            left=e.x_at(region[start]);right=e.x_at(region[end]);y=ty+36+i*30
            pr.draw_rectangle(int(left),int(y),max(1,int(right-left)),13,GREEN)
            pr.draw_text(title,int(left)+11,int(y)+1,10,INK)
        for key,rect in self.time_handles():
            pr.draw_rectangle_rec(pr.Rectangle(*rect),ACCENT)
        pr.draw_text(label(self.state.volume_id+' / drag build and clear handles',e.layout()['w']-52,11),26,int(ty+92),11,INK)

    def wire_segments(self,region,scale=1.):
        ext=[value*scale for value in region['half_extents']]
        yaw=math.radians(region['yaw']);co,si=math.cos(yaw),math.sin(yaw);centre=region['center']
        def world(point):return (centre[0]+co*point[0]-si*point[2],centre[1]+point[1],centre[2]+si*point[0]+co*point[2])
        if region['shape']=='box':
            points=[world(tuple(ext[a]*(1 if index&(1<<a) else -1) for a in range(3))) for index in range(8)]
            return [(points[index],points[index^(1<<axis)]) for index in range(8) for axis in range(3) if (index^(1<<axis))>index]
        rings=[]
        for axis in range(3):
            other=[v for v in range(3) if v!=axis]
            points=[]
            for i in range(49):
                theta=i*math.tau/48;point=[0.,0.,0.]
                point[other[0]]=ext[other[0]]*math.cos(theta);point[other[1]]=ext[other[1]]*math.sin(theta)
                points.append(world(point))
            rings.extend(zip(points,points[1:]))
        return rings

    def draw_guides(self):
        e=self.editor;s=self.state
        if not e.guides or not s.volume or e.selection.enabled:return
        view=e.layout()['viewport'];region=s.volume
        pr.begin_scissor_mode(int(view[0]),int(view[1]),int(view[2]),int(view[3]))
        for scale,colour in ((1.,ACCENT),(region['hollow'],BLUE)):
            if scale<=0:continue
            for start,end in self.wire_segments(region,scale):
                a=e.project(start);b=e.project(end)
                if a is not None and b is not None:pr.draw_line_ex(pr.Vector2(*a),pr.Vector2(*b),1.3,colour)
        pr.draw_rectangle(int(view[0])+5,int(view[1])+5,min(400,int(view[2])-10),35,BG)
        title=s.volume_id+' / '+region['shape']+' / '+('ON' if region['enabled'] else 'OFF')
        pr.draw_text(label(title,view[2]-24,12),int(view[0])+11,int(view[1])+9,12,ACCENT)
        pr.draw_text('Gold: volume bounds   Blue: hollow core',int(view[0])+11,int(view[1])+25,10,BLUE)
        pr.end_scissor_mode()
