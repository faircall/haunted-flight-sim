"""Read-only Moon game facts and live, stateful camera direction.

Scene scripts can register fact providers, remember milestones or emit named
events. Camera rules never mutate the Explorer, puzzle or inventory. Preview
directors use an in-memory document and never poll or write the game profile.
"""
from copy import deepcopy
from pathlib import Path

from g_huxin_moon_direction import DEFAULT_PATH, CameraWatcher, validate_document
from g_scene_cameras import sample_shot, identifier, scalar
from g_camera_rules import CameraRuleEngine
from g_huxin_moon_sequence import ENTRY_DURATION, causeway_progress


def moon_camera_facts(sequence, actor):
    return {
        'world.phase':'teahouse' if sequence.revealed else 'lake',
        'puzzle.solved':bool(sequence.bells or sequence.state!='ordinary'),
        'puzzle.revealed':bool(sequence.revealed), 'puzzle.focused':bool(sequence.focus),
        'player.moving':getattr(actor,'clip','idle') in ('walk','walk_back','run'),
        'player.height':float(actor.height),
        'player.causeway':causeway_progress(actor.x,actor.z),
        'inventory.count':sum(item is not None for item in sequence.inventory),
    }


def _merge_facts(facts,extra):
    if not isinstance(extra,dict):raise ValueError('Fact provider must return a dictionary')
    candidate={**facts,**extra}
    if len(candidate)>512:raise ValueError('Camera facts exceed the combined limit of 512')
    return {identifier(name,'fact name'):scalar(value,'fact value') for name,value in candidate.items()}


class MoonCameraDirector:
    def __init__(self, path=None, document=None):
        self.path=Path(DEFAULT_PATH if path is None else path)
        self.watcher=CameraWatcher(self.path) if document is None else None
        self._document=None if document is None else validate_document(document)
        self.engine=CameraRuleEngine()
        self.next_poll=0.;self.revision=0;self.last_clock=None
        self._observed=None;self.fact_providers=[];self.provider_error=None
        self.fact_overrides={}

    @property
    def document(self):return self._document if self.watcher is None else self.watcher.document
    @property
    def error(self):return self.provider_error or (self.watcher.error if self.watcher else None)
    @property
    def active_id(self):return self.engine.active_id
    @property
    def started(self):return self.engine.started
    @property
    def diagnostics(self):return self.engine.diagnostics
    @property
    def reason(self):return self.engine.reason

    def reset(self, clear_memory=False):
        self.engine.reset(clear_memory=clear_memory);self.last_clock=None
        if clear_memory:self._observed=None;self.fact_overrides.clear()

    def new_visit(self):
        self.engine.new_visit();self.last_clock=None;self._observed=None

    def remember(self,name,value=True):self.engine.remember(name,value)
    def emit(self,name):self.engine.emit(name)

    def register_fact_provider(self,provider):
        """Trusted scene Python: provider(actor, sequence) -> scalar fact dict.

        Providers only read gameplay. For bespoke choreography, emit an event
        from the scene script and let an authored shot hold until its release.
        """
        if not callable(provider):raise TypeError('A camera fact provider must be callable')
        self.fact_providers.append(provider)

    def snapshot_memory(self):
        return {'version':1,'rules':self.engine.export_memory(),'observed':deepcopy(self._observed)}

    def restore_memory(self,memory):
        if not isinstance(memory,dict) or type(memory.get('version')) is not int or memory['version']!=1:
            raise ValueError('Expected camera memory version 1')
        observed=memory.get('observed')
        if observed is not None and (not isinstance(observed,dict) or
            set(observed)!={'puzzle.solved','puzzle.revealed','puzzle.focused'} or
            any(type(value) is not bool for value in observed.values())):
            raise ValueError('Invalid observed camera facts')
        self.engine.import_memory(memory['rules']);self._observed=deepcopy(observed)
        self.last_clock=None

    def use_document(self,document):
        """Update a preview without losing its event history or running move."""
        clean=validate_document(document);changed=clean!=self.document
        self.watcher=None;self._document=clean
        if changed:self.revision+=1
        return changed

    def reload(self,force=False):
        if self.watcher is None:return False
        changed=self.watcher.poll(force=force)
        # File edits must not erase a solved puzzle or replay a once-only shot.
        if changed:self.revision+=1
        return changed

    def update(self,clock):
        if clock>=self.next_poll or (self.last_clock is not None and clock<self.last_clock):
            self.next_poll=clock+.5
            return self.reload()
        return False

    def enabled_slots(self,kind):
        return {s['activation']['index'] for s in self.document['shots']
                if s['enabled'] and s['activation']['type']==kind}

    def trigger_enabled(self,kind):
        return any(s['enabled'] and s['activation']['type']==kind for s in self.document['shots'])

    def observe(self,actor,sequence,clock):
        facts=moon_camera_facts(sequence,actor)
        observed={name:facts[name] for name in ('puzzle.solved','puzzle.revealed','puzzle.focused')}
        previous=self._observed
        if previous is not None:
            if observed['puzzle.solved'] and not previous['puzzle.solved']:self.emit('puzzle.solved')
            if observed['puzzle.revealed']!=previous['puzzle.revealed']:
                self.emit('world.revealed' if observed['puzzle.revealed'] else 'world.returned')
            if observed['puzzle.focused']!=previous['puzzle.focused']:
                self.emit('puzzle.focused' if observed['puzzle.focused'] else 'puzzle.unfocused')
        if observed['puzzle.solved']:
            self.remember('puzzle.solved',True)
            if previous is None:self.remember('event.puzzle.solved.seen',True)
        self._observed=observed
        self.provider_error=None
        for provider in self.fact_providers:
            try:
                facts=_merge_facts(facts,provider(actor,sequence))
            except (ValueError,TypeError,KeyError) as exc:
                self.provider_error='Camera fact provider: '+str(exc)
        if self.watcher is None:
            try:facts=_merge_facts(facts,self.fact_overrides)
            except (ValueError,TypeError,KeyError) as exc:self.provider_error='Camera test facts: '+str(exc)
        return facts

    def camera(self,trigger,actor,sequence,clock,include_zones=True):
        facts=self.observe(actor,sequence,clock)
        shot=self.engine.choose(self.document,trigger,actor,facts,clock,include_zones=include_zones)
        self.last_clock=clock
        if shot is None:return None
        if shot['activation']['type']=='reveal':
            elapsed=sequence.elapsed if sequence.state=='entering' else ENTRY_DURATION
        else:elapsed=max(0.,clock-self.started)
        return shot['id'],sample_shot(shot,elapsed,actor)
