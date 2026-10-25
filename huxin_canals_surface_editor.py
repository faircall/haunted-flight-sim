"""Compact editor panel for geometry-shaped fog and its erosion pattern."""
import math
import pyray as pr
from temple_cinematics_editor import label
from g_huxin_canals_surface_settings import DEFAULT_SURFACE_SETTINGS, TIME_KEYS, surface_blend_window

INK=pr.Color(221,232,229,255);MUTED=pr.Color(133,160,163,255)
ACCENT=pr.Color(228,183,113,255);GREEN=pr.Color(61,119,104,255)


class SurfacePanel:
    def __init__(self,editor):self.editor=editor;self.page='shape'

    @property
    def state(self):return self.editor.state

    def controls(self):
        e=self.editor;s=self.state;x=e.layout()['right']+14;settings=s.surface_settings
        mode=settings.get('evolution','erode');rising=mode!='erode';condensing=mode=='condense'
        buttons=[('surface:enabled','Surface: '+('ON' if settings['enabled'] else 'OFF'),(x,177,131,29),settings['enabled']),
                 ('surface:quality','Quality: '+s.volume_settings['quality'].title(),(x+141,177,131,29),False),
                 ('surface:frame','Frame selected building',(10,565,216,29),False),
                 ('surface:house','Edit this house timing',(10,601,216,29),False)]
        fields=[(('surface','amount'),(x,247,131,30)),(('vol_global','particle_mix'),(x+141,247,131,30))]
        for i,(page,title) in enumerate((('shape','Shape'),('flow','Flow'),('timing','Timing'))):
            buttons.append(('surface:page:'+page,title,(x+i*94,312,86,28),self.page==page))
        if self.page=='shape':
            title={'erode':'Erode','rise_resolve':'Rise / resolve','condense':'Condense'}[mode]
            buttons.append(('surface:evolution','Motion: '+title,(x,357,272,29),rising))
            fields.extend([(('surface',prop),(x+140,y,132,30)) for prop,y in (('density',410),('thickness',452),('edge',494))])
            if rising:fields.append((('surface','initial_scale'),(x+140,536,132,30)))
            if condensing:
                enabled=settings.get('water_mask',False)
                buttons.append(('surface:water_mask','Water veil: '+('ON' if enabled else 'OFF'),(x,584,131,29),enabled))
                wispy=settings.get('wispy_formation',False)
                buttons.append(('surface:wispy_formation','Wispy rise: '+('ON' if wispy else 'OFF'),(x+141,584,131,29),wispy))
        elif self.page=='flow':
            fields.extend([(('surface',prop),(x+140,y,132,30)) for prop,y in (('noise_size',373),('pattern_amount',419))])
            fields.extend([(('surface','wind',i),(x+i*94,501,86,30)) for i in range(3)])
            if condensing:
                fields.append((('surface','wisp_amount'),(x+140,548,132,30)))
                fields.append((('surface','texture_grit'),(x+140,590,132,30)))
                fields.append((('surface','pixel_grain'),(x+140,632,132,30)))
        else:
            buttons.append(('surface:house_timing','House reveal windows: '+('ON' if settings['use_building_timing'] else 'OFF'),(x,357,272,29),settings['use_building_timing']))
            fields.extend([(('surface',prop),(x+i*141,y,131,30)) for props,y in ((TIME_KEYS[:2],432),(TIME_KEYS[2:],508)) for i,prop in enumerate(props)])
            if rising:fields.append((('surface','settle_fraction'),(x+140,554,132,30)))
            if condensing:fields.append((('surface','pull_duration'),(x+140,596,132,30)))
        return buttons,fields

    def field_value(self,path):
        value=self.state.surface_settings.get(path[1],getattr(DEFAULT_SURFACE_SETTINGS,path[1]))
        if path[1] in ('initial_scale','settle_fraction'):value*=100.
        return value[path[2]] if len(path)>2 else value

    def set_field(self,path,value):
        if path[1] in ('initial_scale','settle_fraction'):value/=100.
        self.state.set_surface(path[1],value,path[2] if len(path)>2 else None)

    def action(self,name):
        e=self.editor;s=self.state;settings=s.surface_settings;key=name[8:]
        if key=='enabled':s.set_surface('enabled',not settings['enabled'])
        elif key=='quality':
            values=('draft','balanced','high');s.set_volume_global('quality',values[(values.index(s.volume_settings['quality'])+1)%3])
        elif key.startswith('page:'):self.page=key[5:]
        elif key=='evolution':
            values=('erode','rise_resolve','condense')
            s.set_surface('evolution',values[(values.index(settings.get('evolution','erode'))+1)%len(values)])
        elif key=='house_timing':s.set_surface('use_building_timing',not settings['use_building_timing'])
        elif key=='water_mask':s.set_surface('water_mask',not settings.get('water_mask',False))
        elif key=='wispy_formation':s.set_surface('wispy_formation',not settings.get('wispy_formation',False))
        elif key=='house':e.tab='fog';s.set_fog_mode('buildings')
        elif key=='frame':
            centre=list(s.target.center);size=max(s.target.half_extents)
            e.inspection=dict(eye=[centre[0]+size*1.7,centre[1]+size*1.3,centre[2]+size*2.2],target=centre,fov=58.)
            s.playing=False
        e.status='Surface fog '+('enabled' if s.surface_settings['enabled'] else 'disabled')+' / building surfaces shape the fog; Save keeps your edits.'

    def time_handles(self):
        e=self.editor;y=e.layout()['timeline'][1]
        return [(key,(e.x_at(self.state.surface_settings[key])-8,y+36+(i//2)*30-5,16,23)) for i,key in enumerate(TIME_KEYS)]

    def clamp_time(self,key,value):
        settings=self.state.surface_settings;index=TIME_KEYS.index(key)
        low=0. if index==0 else settings[TIME_KEYS[index-1]]+(.1 if index in (1,3) else 0.)
        cues=self.state.document['cues'];span=cues['blend_end']-cues['build_end']
        if key=='reveal_start':low=max(cues['build_end'],settings['build_end'])+span
        high=self.state.duration if index==3 else settings[TIME_KEYS[index+1]]-(.1 if index in (0,2) else 0.)
        if key=='build_end':high=self.state.duration-span-.1
        return max(low,min(high,value))

    def begin_time_edit(self):
        # A first timeline drag creates the optional section within the drag's
        # own undo transaction; merely opening the panel leaves old files alone.
        if 'surface_fog' not in self.state.document:self.state.document['surface_fog']=self.state.surface_settings

    def draw_labels(self):
        e=self.editor;s=self.state;x=e.layout()['right']+14;settings=s.surface_settings
        mode=settings.get('evolution','erode');rising=mode!='erode';condensing=mode=='condense'
        def text(value,px,py,size=11,colour=MUTED):pr.draw_text(value,int(px),int(py),size,colour)
        text('BUILDING SURFACES',13,444,12,INK)
        text('Follows walls, roofs and stairs.',13,470)
        text('Click a building to inspect its timing.',13,488,10)
        text(label(s.target_id,210,12),13,517,12,ACCENT)
        group=s.document.get('fog',{}).get('groups',{}).get(s.target_id)
        if group:text(f"House {'resolve' if rising else 'clear'}: {group['reveal_start']:.1f} - {group['reveal_end']:.1f} s",13,538)
        text('Surface amount',x,230);text('Shared quad amount',x+141,230)
        blend_start,blend_end=surface_blend_window(s.profile)
        text(f'Geometry blend: {blend_start:.2f} - {blend_end:.2f} s',x,287,10,ACCENT)
        if self.page=='shape':
            for title,y in (('Density',421),('Thickness / metres',463),('Soft edge / fraction',505)):
                text(title,x,y,12,INK)
            if rising:
                text('Initial size / %',x,547,12,INK)
                if condensing:
                    text('Water veil covers water and reflections.',x,636,10)
                    text('Wispy rise connects the lake to the fog.',x,655,10)
                    text('Both follow the authored rise timing.',x,674,10)
                else:
                    text('Grows up from each building footprint.',x,598,10)
                    text('Then settles into its ghostly structure.',x,617,10)
            else:
                text('Thickness expands fog away from surfaces.',x,546,10)
                text('Density controls opacity through its depth.',x,565,10)
        elif self.page=='flow':
            text('Noise size / metres',x,384,12,INK);text('Pattern / 0 to 1',x,430,12,INK)
            text('WIND / metres per second',x,482)
            if condensing:
                text('Lingering wisps / 0-1',x,559,11,INK)
                text('Texture grit / 0-1',x,601,12,INK)
                text('Pixel grain / 0-1',x,643,12,INK)
                text('Coarse grain breaks up the fog edges.',x,685,10)
            else:
                text('Pattern shapes the rising, unsettled fog.' if rising else 'Pattern breaks up growth and clearing.',x,563)
                text('Wind animates the noise in world space.',x,583)
        else:
            text(('RISE' if rising else 'BUILD')+' / seconds',x,403,12,INK)
            text('Starts',x,419,10);text('Full height' if rising else 'Full density',x+141,419,10)
            title=('FALLBACK ' if settings['use_building_timing'] else '')+('RESOLVE' if rising else 'CLEAR')+' / seconds'
            text(title,x,479,12,INK)
            text('Starts',x,495,10);text('Last wisps gone' if condensing else 'Materials visible' if rising else 'Gone',x+141,495,10)
            if condensing:
                text('Pull starts / %',x,565,12,INK)
                text('Pull duration / sec',x,607,12,INK)
                text('Tightening first; material follows the pull.',x,649,10)
                text('Short windows shorten the pull to fit.',x,668,10)
            elif rising:
                text('Ghost settles / %',x,565,12,INK)
                text('First: steady ghost. Then: material detail.',x,608,10)
                text('Houses use their own resolve windows.' if settings['use_building_timing'] else 'All surfaces use this resolve window.',x,627,10)
                text('Other geometry uses the fallback window.',x,646,10)
            else:
                text('Named houses use their own reveal windows.' if settings['use_building_timing'] else 'All surfaces use the clear window above.',x,568,10)
                text('Other geometry uses the fallback window.' if settings['use_building_timing'] else 'Turn house windows on for staggered reveals.',x,587,10)
                text('Drag BUILD / CLEAR handles below to retime.',x,623,10)

    def draw_timeline(self):
        e=self.editor;settings=self.state.surface_settings;ty=e.layout()['timeline'][1]
        mode=settings.get('evolution','erode');rising=mode!='erode';condensing=mode=='condense'
        for i,(start,end,title) in enumerate(((*TIME_KEYS[:2],'RISE' if rising else 'BUILD'),(*TIME_KEYS[2:],'FALLBACK' if settings['use_building_timing'] else 'RESOLVE' if rising else 'CLEAR'))):
            left=e.x_at(settings[start]);right=e.x_at(settings[end]);y=ty+36+i*30
            pr.draw_rectangle(int(left),int(y),max(1,int(right-left)),13,GREEN)
            pr.draw_text(title,int(left)+11,int(y)+1,10,INK)
        for _,rect in self.time_handles():pr.draw_rectangle_rec(pr.Rectangle(*rect),ACCENT)
        title='SURFACE FOG / tighten, inward pull, lingering wisps' if condensing else 'SURFACE FOG / rise, settle, material reveal' if rising else 'SURFACE FOG / build and clearing windows'
        pr.draw_text(title,26,int(ty+92),11,INK)
