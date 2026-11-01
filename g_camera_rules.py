"""Stateful camera selection from validated data, facts and event pulses.

No expressions, callbacks or scene imports are evaluated here. A run owns one
engine; an editor simulation owns another. Memory can be exported as JSON data
without serializing active cameras, clocks or transient event pulses.
"""
from copy import deepcopy
import math
import re

from g_scene_cameras import (CameraValidationError, actor_position, identifier,
                             scalar, validate_document)


def _inside(point,bounds,margin=0.):
    return all(a-margin<=v<=b+margin for a,v,b in zip(bounds['min'],point,bounds['max']))


def _crosses(a,b,bounds):
    """A swept segment must cross the box interior, not merely graze an edge."""
    enter,leave=0.,1.
    for x,y,low,high in zip(a,b,bounds['min'],bounds['max']):
        delta=y-x
        if abs(delta)<1.e-12:
            if not low<x<high:return False
        else:
            u,v=(low-x)/delta,(high-x)/delta
            enter=max(enter,min(u,v));leave=min(leave,max(u,v))
            if leave-enter<=1.e-9:return False
    return leave-enter>1.e-9


def _facts(values):
    if not isinstance(values,dict) or len(values)>512:raise CameraValidationError('facts: expected an object with at most 512 values')
    return {identifier(k,'fact name'):scalar(v,'fact '+str(k)) for k,v in values.items()}


def _names(values,path,limit=512):
    if not isinstance(values,(list,tuple,set,frozenset)) or len(values)>limit:
        raise CameraValidationError(path+': expected a bounded list of names')
    return tuple(dict.fromkeys(identifier(value,path) for value in values))


def _shot_ids(values,path):
    if not isinstance(values,list) or len(values)>4096 or any(
        not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}',value) for value in values):
        raise CameraValidationError(path+': expected a bounded list of camera IDs')
    return set(values)


def _condition(condition,facts):
    name=condition['fact'];op=condition['op'];wanted=condition['value']
    if name not in facts:return False,'Missing fact: '+name
    actual=facts[name]
    numeric=lambda v:isinstance(v,(int,float)) and type(v) is not bool
    compatible=(numeric(actual) and numeric(wanted)) or type(actual) is type(wanted)
    if op=='eq':passed=compatible and actual==wanted
    elif op=='ne':passed=not compatible or actual!=wanted
    elif not numeric(actual):passed=False
    elif op=='gte':passed=actual>=wanted
    else:passed=actual<=wanted
    return passed,('Condition matched: ' if passed else 'Condition failed: ')+name+' '+op+' '+repr(wanted)


class CameraRuleEngine:
    def __init__(self):
        self._source=None;self._document=None
        self._remembered={};self._remembered_events=set();self._seen_run=set();self._seen_visit=set()
        self._pending=[];self._deferred=set();self.history=[]
        self._released={};self._completed=set();self._markers={}
        self.reset(clear_memory=True)

    def reset(self,clear_memory=False):
        """Release transient camera state; only an explicit reset starts a run."""
        self.active_id=None;self.started=0.;self.reason='No active camera';self.diagnostics=[]
        self.facts={};self.events=();self._clock=None;self._step=0;self._activation_step=-1
        self._release_requested=None
        if clear_memory:
            self._remembered.clear();self._remembered_events.clear();self._seen_run.clear();self._seen_visit.clear();self.history.clear()
            self._released.clear();self._completed.clear();self._markers.clear();self._pending.clear();self._deferred.clear()

    def new_visit(self):
        self.reset();self._seen_visit.clear()
        self._released.clear();self._completed.clear();self._markers.clear();self._pending.clear();self._deferred.clear()

    def remember(self,name,value=True):
        name=identifier(name,'remembered fact');value=scalar(value,'remembered fact value')
        if name not in self._remembered and len(self._remembered)>=512:raise CameraValidationError('At most 512 remembered facts are supported')
        self._remembered[name]=value

    def emit(self,name):
        name=identifier(name,'event')
        if name not in self._pending:
            if len(self._pending)>=512:raise CameraValidationError('At most 512 pending events are supported')
            self._pending.append(name)

    def export_memory(self):
        return dict(version=1,remembered=deepcopy(self._remembered),events=sorted(self._remembered_events),
                    seen_run=sorted(self._seen_run),seen_visit=sorted(self._seen_visit))

    def import_memory(self,memory):
        if not isinstance(memory,dict) or set(memory)!= {'version','remembered','events','seen_run','seen_visit'}:
            raise CameraValidationError('Camera memory has an unknown format')
        if type(memory['version']) is not int or memory['version']!=1:raise CameraValidationError('Unsupported camera memory version')
        if not isinstance(memory['events'],list):raise CameraValidationError('Remembered events must be a JSON list')
        remembered=_facts(memory['remembered']);events=set(_names(memory['events'],'remembered events'))
        run=_shot_ids(memory['seen_run'],'seen run shots');visit=_shot_ids(memory['seen_visit'],'seen visit shots')
        self.reset(clear_memory=True)
        self._remembered=remembered;self._remembered_events=events;self._seen_run=run;self._seen_visit=visit

    def _record(self,kind,clock,**values):
        self.history.append(dict(type=kind,clock=clock,**values));self.history=self.history[-160:]

    def _document_for(self,source):
        # Equality detects in-place editor edits as well as replaced watcher
        # documents. Validation only runs when authored data actually changes.
        if source!=self._source:
            document=validate_document(source)
            self._source=deepcopy(source);self._document=document
        return self._document

    def _sample_markers(self,document,position,phase,rewound=False):
        # Compute the next sample first, so a full event/fact history can reject
        # a new pulse without consuming occupancy or pending events.
        emitted=[];facts={};next_markers={};visits=set()
        for marker in document['markers']:
            name=marker['id'];prefix='marker.'+name;allowed=marker['phase'] in ('any',phase)
            inside=allowed and _inside(position,marker['bounds']);previous=None if rewound else self._markers.get(name)
            shape=(marker['phase'],tuple(marker['bounds']['min']),tuple(marker['bounds']['max']))
            # A new or edited marker establishes occupancy without inventing
            # an entry event for an actor already standing in the box.
            if previous is not None and previous['shape']==shape:
                if previous['inside'] and not inside:emitted.append(prefix+'.exited')
                elif previous['allowed'] and allowed:
                    if not previous['inside'] and inside:emitted.append(prefix+'.entered')
                    elif not previous['inside'] and not inside and _crosses(previous['position'],position,marker['bounds']):
                        emitted.extend((prefix+'.entered',prefix+'.exited'))
            if inside or prefix+'.entered' in emitted:visits.add(prefix+'.visited')
            facts[prefix+'.inside']=bool(inside)
            facts[prefix+'.visited']=prefix+'.visited' in visits or bool(self._remembered.get(prefix+'.visited',False))
            next_markers[name]=dict(position=list(position),inside=inside,allowed=allowed,shape=shape)
        return emitted,facts,next_markers,visits

    def _visible_memory(self,document):
        # Keep historical marker visits in exported run memory for undo/reload,
        # but a condition on a deleted marker must fail closed in this profile.
        marker_ids={marker['id'] for marker in document['markers']}
        return {name:value for name,value in self._remembered.items() if not (
            name.startswith('marker.') and name.endswith('.visited') and name[7:-8] not in marker_ids)}

    def _activation(self,shot,trigger,position,phase,include_zones):
        active=shot['activation'];kind=active['type'];requested=trigger['type']
        if kind in ('zone','rule'):
            if requested not in ('lake','room'):return False,'Reserved puzzle camera'
            if not include_zones:return False,'Automatic rules bypassed'
            if active['phase'] not in ('any',phase):return False,'Different world phase'
            if kind=='zone':
                margin=shot['rule']['exit_margin'] if shot['id']==self.active_id else 0.
                if not _inside(position,active['bounds'],margin):return False,'Outside zone'
            return True,'Rule trigger matched' if kind=='rule' else 'Inside zone'
        if kind!=requested or (kind in ('lake','room') and active['index']!=trigger.get('index')):
            return False,'Different scene camera'
        return True,'Scene trigger matched'

    def _base_eligibility(self,shot,trigger,position,phase,facts,include_zones):
        if not shot['enabled']:return False,'Disabled'
        matched,reason=self._activation(shot,trigger,position,phase,include_zones)
        if not matched:return False,reason
        for condition in shot['rule']['conditions']:
            passed,reason=_condition(condition,facts)
            if not passed:return False,reason
        return True,'Eligible'

    def _release(self,clock,reason,completed=False):
        if self.active_id is not None:
            identity=self.active_id;self._released[identity]=clock
            if completed:self._completed.add(identity)
            self._record('released',clock,id=identity,reason=reason)
        self.active_id=None;self._release_requested=None

    def choose(self,document,trigger,actor,facts,clock,events=(),include_zones=True):
        """Evaluate one frame. Events are pulses; ordinary facts are levels.

        A duration/event hold finishes once and waits for a fresh trigger edge
        (or a new start event) before replaying. Cooldown starts on release.
        Equal-priority candidates retain the current camera to avoid chatter.
        """
        if not isinstance(trigger,dict) or trigger.get('type') not in ('lake','room','focus','reveal'):
            raise CameraValidationError('Unknown scene camera trigger')
        if trigger['type'] in ('lake','room') and (type(trigger.get('index')) is not int or trigger['index']< -1):
            raise CameraValidationError('Indexed scene cameras need a nonnegative index, or -1 when no base slot is enabled')
        position=actor_position(actor);incoming=_facts(facts);incoming_events=_names(events,'events')
        if isinstance(clock,bool) or not isinstance(clock,(int,float)):
            raise CameraValidationError('Camera clock must be finite and nonnegative')
        try:clock=float(clock)
        except (ValueError,OverflowError):raise CameraValidationError('Camera clock must be finite and nonnegative') from None
        if not math.isfinite(clock) or not 0.<=clock<=1.e12:raise CameraValidationError('Camera clock must be finite and nonnegative')
        if type(include_zones) is not bool:raise CameraValidationError('include_zones must be a boolean')
        doc=self._document_for(document)
        rewound=self._clock is not None and clock<self._clock
        merged={**self._visible_memory(doc),**incoming}
        phase=merged.get('world.phase',merged.get('scene.phase',merged.get('phase','teahouse' if trigger['type']=='room' else 'lake')))
        marker_events,marker_facts,next_markers,visits=self._sample_markers(doc,position,phase,rewound)
        pulses=list(dict.fromkeys((*self._pending,*incoming_events,*marker_events)));deferred=set(self._deferred)
        if not include_zones:
            starts={s['rule']['start_event'] for s in doc['shots'] if s['activation']['type'] in ('zone','rule')}
            deferred.update(event for event in pulses if event in starts)
        elif deferred and trigger['type'] in ('lake','room'):
            pulses=list(dict.fromkeys((*pulses,*sorted(deferred))));deferred.clear()
        if len(self._remembered_events|set(pulses))>512:
            raise CameraValidationError('Camera event memory is full (512 distinct names); reset the run before introducing more event names')
        if len(set(self._remembered)|visits)>512:
            raise CameraValidationError('Camera fact memory is full (512 values); reset the run before adding marker visits')
        possible_ids={s['id'] for s in doc['shots'] if s['enabled']}
        if len(self._seen_run|possible_ids)>4096 or len(self._seen_visit|possible_ids)>4096:
            raise CameraValidationError('Camera shot history is full; reset its run or visit before loading more distinct shot IDs')
        # All external input and bounded memory growth have been checked before
        # advancing clocks, consuming pulses or changing marker occupancy.
        if rewound:
            self.reset();self._released.clear();self._completed.clear()
        self._clock=clock;self._step+=1;self._pending.clear();self._deferred=deferred;self._markers=next_markers
        self._remembered.update({name:True for name in visits})
        self.events=tuple(pulses)
        for name in pulses:
            self._remembered_events.add(name);self._record('event',clock,name=name)
        # A finite history of event names can be persisted independently from
        # the current pulse list. The scene's scalar facts override remembered
        # values; computed marker state cannot be accidentally spoofed by them.
        merged={**self._visible_memory(doc),**incoming,**marker_facts}
        merged.update({'event.'+name+'.seen':True for name in self._remembered_events})
        self.facts=merged
        by_id={s['id']:s for s in doc['shots']};active=by_id.get(self.active_id)
        bases={s['id']:self._base_eligibility(s,trigger,position,phase,merged,include_zones) for s in doc['shots']}
        blocked_now=set();held=False;hold_reason='';prior_id=self.active_id
        if self.active_id is not None:
            special=trigger['type'] in ('focus','reveal')
            context_ok=active is not None and (
                active['activation']['type']==trigger['type'] if special else active['activation']['type'] not in ('focus','reveal'))
            manual_ok=active is not None and (include_zones or active['activation']['type'] not in ('zone','rule'))
            if active is not None and not include_zones and active['activation']['type'] in ('lake','room'):
                manual_ok=active['activation']['type']==trigger['type'] and active['activation']['index']==trigger.get('index')
            if active is None or not active['enabled'] or not context_ok or not manual_ok:
                self._release(clock,'Camera disabled, removed or scene context changed')
            else:
                rule=active['rule'];age=max(0.,clock-self.started)
                if self._step>self._activation_step and rule['release_event'] and rule['release_event'] in pulses:
                    self._release_requested='Release event: '+rule['release_event']
                if rule['hold']=='duration' and age>=active['duration']:
                    self._release_requested=self._release_requested or 'Shot duration completed'
                if age<rule['min_hold']:
                    held=True;hold_reason=f"Minimum hold: {rule['min_hold']-age:.2f}s remaining"
                elif self._release_requested:
                    blocked_now.add(active['id']);self._release(clock,self._release_requested,completed=True)
                elif rule['hold']=='duration':
                    held=True;hold_reason=f"Duration hold: {active['duration']-age:.2f}s remaining"
                elif rule['hold']=='event':
                    held=True;hold_reason='Waiting for release event: '+(rule['release_event'] or '(not set)')
                elif not bases[active['id']][0]:self._release(clock,bases[active['id']][1])

        candidates=[];self.diagnostics=[]
        for order,shot in enumerate(doc['shots']):
            identity=shot['id'];rule=shot['rule'];eligible,reason=bases[identity];is_active=identity==self.active_id
            if not eligible:self._completed.discard(identity)
            if is_active and held:eligible=True;reason=hold_reason
            if eligible and not is_active:
                if identity in blocked_now:eligible=False;reason='Released this frame'
                elif rule['repeat']=='run' and identity in self._seen_run:eligible=False;reason='Already played this run'
                elif rule['repeat']=='visit' and identity in self._seen_visit:eligible=False;reason='Already played this visit'
                elif clock<self._released.get(identity,-math.inf)+rule['cooldown']:
                    eligible=False;reason='Cooling down'
                elif rule['start_event'] and rule['start_event'] not in pulses:eligible=False;reason='Waiting for event: '+rule['start_event']
                elif identity in self._completed and not (rule['start_event'] and rule['start_event'] in pulses):
                    eligible=False;reason='Completed; waiting for a new trigger'
            priority=shot['activation']['priority']
            self.diagnostics.append(dict(id=identity,label=shot['label'],eligible=bool(eligible),reason=reason,priority=priority,active=False))
            if eligible:candidates.append((priority,is_active,-order,shot))
        chosen=max(candidates,key=lambda item:item[:3])[3] if candidates else None
        if held and self.active_id is not None:
            held_shot=by_id[self.active_id];priority=held_shot['activation']['priority']
            interrupts=[item for item in candidates if item[0]>priority and item[3]['rule']['interrupt']]
            chosen=max(interrupts,key=lambda item:item[:3])[3] if interrupts else held_shot
        if chosen is not None and chosen['id']!=self.active_id:
            if self.active_id is not None:self._release(clock,'Preempted by '+chosen['id'])
            self.active_id=chosen['id'];self.started=clock;self._activation_step=self._step;self._release_requested=None
            self._seen_run.add(self.active_id);self._seen_visit.add(self.active_id);self._completed.discard(self.active_id)
            self._record('activated',clock,id=self.active_id,label=chosen['label'])
        elif chosen is None and self.active_id is not None:self._release(clock,'No eligible camera')
        if chosen is None:self.reason='No eligible camera'
        elif held and chosen['id']==prior_id:self.reason=hold_reason
        elif chosen['id']==prior_id:self.reason='Keeping eligible camera'
        else:self.reason='Selected highest-priority eligible camera'
        for row in self.diagnostics:
            row['active']=row['id']==self.active_id
            if row['active']:row['reason']=self.reason
        return chosen
