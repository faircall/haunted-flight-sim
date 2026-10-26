"""Live authored Moon shots, independent of the native editor and renderer."""
from pathlib import Path

from g_huxin_moon_direction import DEFAULT_PATH, CameraWatcher
from g_scene_cameras import resolve_shot, sample_shot
from g_huxin_moon_sequence import ENTRY_DURATION


class MoonCameraDirector:
    def __init__(self, path=None):
        self.path=Path(DEFAULT_PATH if path is None else path)
        self.watcher=CameraWatcher(self.path)
        self.active_id=None
        self.started=0.
        self.last_clock=None
        self.next_poll=0.
        self.revision=0

    @property
    def document(self):return self.watcher.document

    @property
    def error(self):return self.watcher.error

    def reset(self):
        self.active_id=None;self.started=0.;self.last_clock=None

    def reload(self,force=False):
        changed=self.watcher.poll(force=force)
        if changed:
            self.reset();self.revision+=1
        return changed

    def update(self,clock):
        if clock>=self.next_poll or (self.last_clock is not None and clock<self.last_clock):
            self.next_poll=clock+.5
            return self.reload()
        return False

    def camera(self,trigger,actor,sequence,clock,include_zones=True):
        phase='teahouse' if sequence.revealed else 'lake'
        document=self.document
        if not include_zones:
            document={**document,'shots':[s for s in document['shots'] if s['activation']['type']!='zone']}
        shot=resolve_shot(document,trigger,actor,phase)
        if shot is None:
            self.reset()
            return None
        if self.active_id!=shot['id'] or (self.last_clock is not None and clock<self.last_clock):
            self.active_id=shot['id'];self.started=clock
        self.last_clock=clock
        if trigger['type']=='reveal':
            elapsed=sequence.elapsed if sequence.state=='entering' else ENTRY_DURATION
        else:elapsed=max(0.,clock-self.started)
        return shot['id'],sample_shot(shot,elapsed,actor)
