"""Rule, marker and isolated director-testing panels for the native editor."""
from copy import deepcopy
import json
import math
import pyray as pr
from temple_cinematics_editor import label
from g_huxin_moon import DECK
from g_huxin_moon_sequence import causeway_point


def scalar(text):
    """A literal JSON scalar or plain string, never executable source."""
    try:value=json.loads(text)
    except (ValueError,TypeError):value=text
    if not isinstance(value,(str,bool,int,float)) or isinstance(value,float) and not math.isfinite(value):
        raise ValueError('Use true, false, a finite number, or text; lists/objects are not facts.')
    return value


class DirectorPanel:
    def __init__(self,editor):
        self.editor=editor;self.condition=0;self.marker_id=None;self.marker_page=0
        self.testing=False;self.director=None;self.clock=0.;self.overrides={};self.phase='lake'
        self.event_text='puzzle.solved';self.fact_text='puzzle.solved';self.value_text='true'
        self.last_pose=None;self.simulation_ticks=0

    @property
    def markers(self):return self.editor.state.document.get('markers',[])
    @property
    def marker(self):
        if not self.markers:self.marker_id=None;return None
        marker=next((m for m in self.markers if m['id']==self.marker_id),self.markers[0]);self.marker_id=marker['id'];return marker

    def text_field(self,path):
        return path[0]=='test' or path[-1] in ('fact','start_event','release_event','id','label')

    def scalar_field(self,path):return len(path)>2 and path[0]=='rule' and path[-1]=='value'

    def field_value(self,path):
        if path[0]=='test':return getattr(self,path[1]+'_text')
        if path[0]=='marker':
            value=self.marker
            for part in path[1:]:value=value[part]
            return value
        raise KeyError(path)

    def set_value(self,path,value):
        if path[0]=='test':setattr(self,path[1]+'_text',str(value));return
        identity=self.marker['id']
        def change(document):
            node=next(m for m in document['markers'] if m['id']==identity)
            for part in path[1:-1]:node=node[part]
            node[path[-1]]=value
            if path==('marker','id'):
                old='marker.'+identity+'.';new='marker.'+str(value)+'.'
                def renamed(name):
                    if name.startswith(old):return new+name[len(old):]
                    if name.startswith('event.'+old):return 'event.'+new+name[len('event.'+old):]
                    return name
                for shot in document['shots']:
                    rule=shot['rule']
                    for prop in ('start_event','release_event'):rule[prop]=renamed(rule[prop])
                    for condition in rule['conditions']:condition['fact']=renamed(condition['fact'])
        self.editor.state.change_document(change)
        if path==('marker','id'):self.marker_id=value

    def controls(self,buttons,fields,labels):
        e=self.editor;a=e.layout();x=a['right']+14;shot=e.state.shot
        for i,(name,title) in enumerate((('rules','RULES'),('timing','TIMING'),('markers','MARKERS'))):
            buttons.append(('tab:'+name,title,(x+i*104,106,102 if i==2 else 96,29),e.tab==name))
        buttons.append(('test_director','Test director: ON' if self.testing else 'Test director',(a['left']+372,71,158,31),self.testing))
        def field(path,title,y,width=310,x0=x):labels.append((title,x0,y-17));fields.append((path,(x0,y,width,30)))
        def vector(path,title,y):
            labels.append((title,x,y-17))
            for i in range(3):fields.append((path+(i,),(x+i*106,y,98,30)))
        if e.tab=='rules':
            rule=shot['rule'];conditions=rule['conditions']
            field(('rule','start_event'),'START EVENT / blank means no event gate',168)
            labels.append(('ALL CONDITIONS MUST MATCH',x,216))
            self.condition=max(0,min(self.condition,len(conditions)-1))
            page=self.condition//4
            for i,c in enumerate(conditions[page*4:page*4+4],page*4):
                text=f"{c['fact']} {c['op']} {json.dumps(c['value'],ensure_ascii=False)}"
                buttons.append(('condition:'+str(i),text,(x,238+(i%4)*31,310,27),i==self.condition))
            buttons.extend([('condition_add','Add condition',(x,375,150,29),False),('condition_remove','Remove',(x+160,375,150,29),False),
                            ('condition_previous','<',(x,410,42,26),False),('condition_next','>',(x+268,410,42,26),False)])
            labels.append((f'Condition {self.condition+1 if conditions else 0} / {len(conditions)}',x+57,418))
            if conditions:
                field(('rule','conditions',self.condition,'fact'),'FACT / built-in, marker or custom name',467)
                buttons.append(('condition_op','Compare: '+conditions[self.condition]['op'],(x,510,310,29),False))
                field(('rule','conditions',self.condition,'value'),'VALUE / true, false, number or text',576)
            buttons.append(('tracking_sample','Add after-puzzle tracking sample',(x,640,310,31),False))
            labels.extend([('Sample adds a shot and two causeway markers.',x,690),('Nothing is inserted or saved automatically.',x,712)])
        elif e.tab=='timing':
            rule=shot['rule']
            for prop,title,y in (('repeat','Repeat',155),('hold','Hold until',199),('interrupt','May interrupt a held shot',243)):
                value=('ON' if rule[prop] else 'OFF') if prop=='interrupt' else str(rule[prop]).title()
                buttons.append(('rule_cycle:'+prop,title+': '+value,(x,y,310,31),False))
            field(('rule','min_hold'),'MINIMUM HOLD / seconds',321)
            field(('rule','cooldown'),'COOLDOWN / seconds after release',386)
            field(('rule','exit_margin'),'EXIT MARGIN / metres around zone',451)
            field(('rule','release_event'),'RELEASE EVENT / used by Event hold',516)
            labels.extend([('Always: can repeat. Visit: once per visit.',x,579),('Run: once until memory is reset.',x,601),
                           ('Eligible: release when conditions stop matching.',x,635),('Duration: hold for the shot move duration.',x,657),
                           ('Event: hold until the release event arrives.',x,679),('Higher priority only breaks a hold if Interrupt ON.',x,711)])
        elif e.tab=='markers':
            markers=self.markers;pages=max(1,math.ceil(len(markers)/4));self.marker_page=min(self.marker_page,pages-1)
            for i,marker in enumerate(markers[self.marker_page*4:self.marker_page*4+4]):
                buttons.append(('marker:'+marker['id'],marker['label'],(x,153+i*31,310,27),marker['id']==self.marker_id))
            buttons.extend([('marker_add','Add marker',(x,286,150,29),False),('marker_remove','Remove marker',(x+160,286,150,29),False),
                            ('marker_previous','<',(x,323,42,25),False),('marker_next','>',(x+268,323,42,25),False)])
            labels.append((f'Markers / {self.marker_page+1} of {pages}',x+59,330))
            marker=self.marker
            if marker:
                field(('marker','id'),'ID / used in marker.<id>.entered',381)
                field(('marker','label'),'LABEL',443)
                buttons.append(('marker_phase','World: '+marker['phase'].title(),(x,487,310,29),False))
                vector(('marker','bounds','min'),'MINIMUM / X Y Z',552)
                vector(('marker','bounds','max'),'MAXIMUM / X Y Z',615)
                buttons.append(('marker_actor','Centre on test actor',(x,665,310,30),False))
                labels.append(('Entering/exiting emits events; visited is remembered.',x,721))
        if self.testing:
            lx=a['left']+18;cy=a['bottom']-266
            field(('test','event'),'TEST EVENT / transient pulse',cy,width=313,x0=lx)
            buttons.extend([('test_emit','Emit event',(lx+323,cy,104,30),False),('test_solved','Puzzle solved',(lx+437,cy,130,30),False)])
            field(('test','fact'),'TEST FACT / name',cy+58,width=203,x0=lx)
            field(('test','value'),'VALUE',cy+58,width=100,x0=lx+213)
            buttons.extend([('test_remember','Set fact',(lx+323,cy+58,104,30),False),
                            ('test_reset','Reset memory',(lx+437,cy+58,130,30),False),('test_visit','New visit',(lx+577,cy+58,121,30),False)])

    def reset(self,clear=True):
        if clear:self.overrides.clear()
        if self.director is not None:
            self.director.reset(clear_memory=clear)
            self.director.use_document(self.editor.state.document)
            self.director.fact_overrides=dict(self.overrides)
        self.clock=self.editor.state.elapsed;self.last_pose=None;self.simulation_ticks=0

    def start_test(self):
        from huxin_moon_camera_runtime import MoonCameraDirector
        self.director=MoonCameraDirector(document=deepcopy(self.editor.state.document))
        self.phase=self.editor.state.shot['preview']['phase'];self.testing=True;self.editor.preview=True;self.editor.state.playing=False;self.reset()

    def action(self,name):
        e=self.editor;shot=e.state.shot
        if name=='test_director':
            if self.testing:self.testing=False;e.preview=False;e.state.playing=False
            else:self.start_test()
        elif name.startswith('condition:'):self.condition=int(name.split(':')[1])
        elif name=='condition_add':
            e.state.change(lambda shot:shot['rule']['conditions'].append({'fact':'puzzle.solved','op':'eq','value':True}));self.condition=len(e.state.shot['rule']['conditions'])-1
        elif name=='condition_remove':
            if shot['rule']['conditions']:e.state.change(lambda shot:shot['rule']['conditions'].pop(self.condition));self.condition=max(0,self.condition-1)
        elif name in ('condition_previous','condition_next'):
            self.condition=max(0,min(len(shot['rule']['conditions'])-1,self.condition+(-1 if name.endswith('previous') else 1)))
        elif name=='condition_op':
            values=('eq','ne','gte','lte');path=('rule','conditions',self.condition,'op');old=e.field_value(path);e.set_value(path,values[(values.index(old)+1)%4])
        elif name.startswith('rule_cycle:'):
            prop=name.split(':')[1];old=shot['rule'][prop]
            if prop=='interrupt':value=not old
            else:
                values=('always','visit','run') if prop=='repeat' else ('eligible','duration','event');value=values[(values.index(old)+1)%3]
            e.set_value(('rule',prop),value)
        elif name.startswith('marker:'):self.marker_id=name[7:]
        elif name=='marker_add':
            marker=e.state.add_marker();self.marker_id=marker['id'];self.marker_page=(len(self.markers)-1)//4
        elif name=='marker_remove':
            if self.marker:e.state.remove_marker(self.marker['id']);self.marker_id=None
        elif name in ('marker_previous','marker_next'):self.marker_page=max(0,self.marker_page+(-1 if name.endswith('previous') else 1))
        elif name=='marker_phase':
            values=('any','lake','teahouse');self.set_value(('marker','phase'),values[(values.index(self.marker['phase'])+1)%3])
        elif name=='marker_actor':
            low,high=self.marker['bounds']['min'],self.marker['bounds']['max'];center=(e.actor.x,e.actor.height+1.,e.actor.z)
            self.set_value(('marker','bounds'),{'min':[v-(b-a)*.5 for v,a,b in zip(center,low,high)],'max':[v+(b-a)*.5 for v,a,b in zip(center,low,high)]})
        elif name=='tracking_sample':self.add_sample()
        elif name in ('test_emit','test_remember','test_reset','test_visit','test_solved'):
            if not self.testing:self.start_test()
            if name=='test_emit':self.director.engine.emit(self.event_text);e.status='Emitted '+self.event_text+' in the isolated preview.'
            elif name=='test_remember':
                value=scalar(self.value_text);self.director.engine.remember(self.fact_text,value);self.overrides[self.fact_text]=value
                self.director.fact_overrides=dict(self.overrides);e.status='Test fact set: '+self.fact_text
            elif name=='test_reset':self.reset();e.status='Preview event memory and once-only history cleared.'
            elif name=='test_visit':self.director.new_visit();e.status='New preview visit; per-run memory retained.'
            else:
                self.overrides['puzzle.solved']=True;self.director.fact_overrides=dict(self.overrides);self.director.engine.emit('puzzle.solved')
                e.status='Puzzle solved event/fact simulated; geometry is controlled by Scene preview.'
        else:return False
        return True

    def add_sample(self):
        e=self.editor;shot=deepcopy(e.state.shot);ids={s['id'] for s in e.state.document['shots']}|{m['id'] for m in self.markers}
        def unique(base):
            value=base;n=2
            while value in ids:value=f'{base}-{n}';n+=1
            ids.add(value);return value
        start_id,end_id=unique('tracking-start'),unique('tracking-end');identity=unique('after-puzzle-tracking')
        start=causeway_point(.90);end=causeway_point(.72);spawn=causeway_point(.95)
        markers=[]
        for ident,title,(x,z) in ((start_id,'Tracking begins',start),(end_id,'Tracking ends',end)):
            markers.append({'id':ident,'label':title,'phase':'any','bounds':{'min':[x-1.3,DECK-.2,z-1.8],'max':[x+1.3,DECK+2.4,z+1.8]}})
        actor=[spawn[0],DECK,spawn[1]];frame={'eye':[actor[0]+4.,DECK+3.1,actor[2]+5.],
              'target':[actor[0],DECK+.95,actor[2]],'fov':64.}
        rule={'conditions':[{'fact':'puzzle.solved','op':'eq','value':True}],
              'start_event':f'marker.{start_id}.entered','repeat':'visit','min_hold':1.,'hold':'event',
              'release_event':f'marker.{end_id}.entered','interrupt':False,'cooldown':2.,'exit_margin':.25}
        shot.update(id=identity,label='After puzzle tracking',enabled=True,activation={'type':'rule','phase':'any','priority':50},
                    movement='follow',aim='player',lens='fixed',easing='smooth',duration=8.,start=deepcopy(frame),end=deepcopy(frame),
                    preview={'phase':'teahouse','actor':actor,'yaw':math.atan2(end[0]-spawn[0],-(end[1]-spawn[1]))},aim_offset=[0.,.95,0.],rule=rule)
        def add(document):document['shots'].append(shot);document['markers'].extend(markers)
        e.state.change_document(add);self.testing=False;e.select(identity);e.tab='rules';self.marker_id=start_id
        e.status='Sample added: Test director, Puzzle solved, then walk out. Once per visit; New visit re-arms it. Save to keep it.'

    def sample(self):
        e=self.editor
        if self.director is None:self.start_test()
        self.director.use_document(e.state.document);self.director.fact_overrides=dict(self.overrides)
        from huxin_moon_viewer import gameplay_camera,safety_camera
        trigger,index,fallback=gameplay_camera(e.actor,e.sequence,self.director)
        result=self.director.camera(trigger,e.actor,e.sequence,self.clock)
        if result is None:
            fallback=safety_camera(e.actor)[1]
            frame={'eye':[fallback.position.x,fallback.position.y,fallback.position.z],
                   'target':[fallback.target.x,fallback.target.y,fallback.target.z],'fov':fallback.fovy}
        else:frame=result[1]
        self.last_pose=frame;self.simulation_ticks+=1
        return frame

    def draw_diagnostics(self,colour,muted):
        if not self.testing or self.director is None:return
        e=self.editor;a=e.layout();x=a['left']+18;y=a['bottom']-160;width=a['right']-x-18
        engine=self.director.engine;active=getattr(self.director,'active_id',None) or 'safety camera'
        pr.draw_text(label(f'ACTIVE: {active} / test clock {self.clock:.1f}s',width,12),x,y,12,colour)
        reason=self.director.error or getattr(engine,'reason','')
        pr.draw_text(label(str(reason),width,11),x,y+18,11,muted)
        rows=getattr(engine,'diagnostics',[])
        rivals=[r for r in rows if not r.get('active')]
        rivals.sort(key=lambda r:(not r.get('eligible',False),-r.get('priority',0)))
        selected=next((r for r in rivals if r['id']==e.state.selected),None)
        if selected:rivals=[selected]+[r for r in rivals if r is not selected]
        for i,row in enumerate(rivals[:2]):
            text=f"{row['label']} / priority {row['priority']}: {row['reason']}"
            pr.draw_text(label(text,width,10),x,y+35+i*14,10,muted)
        value=getattr(engine,'facts',{}).get(self.fact_text,'(missing)')
        latest=next((row.get('name','') for row in reversed(getattr(engine,'history',[])) if row.get('type')=='event'),'none')
        text=f'Fact {self.fact_text}: {json.dumps(value,ensure_ascii=False)} / last event: {latest}'
        pr.draw_text(label(text,width,10),x,y+68,10,muted)
