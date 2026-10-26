"""Moon camera defaults and JSON authoring, with no renderer dependencies.

Missing files use the original camera stations. Only an explicit save creates
the profile; a watcher never writes, and malformed edits retain its last good
document. CameraDocument additionally protects unsaved work from outside edits.
"""
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile

from g_scene_cameras import CameraValidationError, validate_document as validate_cameras

DEFAULT_PATH=Path(__file__).resolve().parent/'art'/'temple'/'huxin_moon'/'cameras.json'
MAX_BYTES=2*1024*1024

# Copies of the existing stations, deliberately independent of native imports.
LAKE_SHOTS=(
 ('A pavilion in the mist',(-8.2,4.,86),(-11,1.9,66),66),
 ('Leaving the pines',(-18,3.2,67),(-9,2.2,49),69),
 ('Water on every side',(1,3.3,49),(-7,2.5,33),70),
 ('The long approach',(-12,2.85,28),(0,3.8,3),71),
 ('Under the flying eaves',(9.5,3.5,14),(0,3.9,.5),75),
 ('The empty centre',(4.05,3.2,3.05),(-.7,1.5,-1.2),78),
 ('Only the path home',(3.5,3.1,-3.5),(-1,2.1,7),78),
 ('The far shore fades',(-11,3.2,-12),(0,4.4,0),65),
 ('Reflected in the lake',(20,2.,23),(0,4.,0),56),
)
ROOM_SHOTS=(
 ('The room within the pavilion',(5.9,3.35,5.35),(0,1.5,0),73),
 ('Three empty chairs',(11.7,3.15,2.65),(9.5,1.1,-.3),74),
 ('The timber stair',(-5.65,7.1,-5.4),(-5.65,2.8,1.8),72),
 ('Upper gallery',(-3.85,6.95,5.4),(1.2,5.2,-1.5),76),
 ('The empty tray',(6.35,6.65,-2.55),(4.7,5.1,-4.5),80),
 ('Water beyond the balcony',(5.9,6.5,7.7),(0,5.1,7.3),75),
 ('A house upon the water',(25,10,28),(1,5,0),60),
 ('The narrow landing',(-3.1,6.85,-5.25),(-5.4,5.1,-4.7),75),
 ('The other side of the hall',(-3.95,3.45,-4.7),(.8,1.5,1),76),
 ('The open doorway',(.15,3.30,4.4),(0,1.2,7),76),
 ('The eastern gallery',(6.25,6.9,5.2),(3,5.1,1),76),
)
LAKE_ACTORS=((-12.45,.715,82),(-10.5,.325,60),(-8,.325,43),(-4.5,.325,29),
             (-2,.325,11),(1,.325,1),(0,.325,5.8),(0,.325,-1.5),(1,.325,1))
ROOM_ACTORS=((0,.325,1.8),(8,.325,1),(-5.65,.325+9*3.8/22,1),(0,4.125,1),(5.8,4.125,-2.6),
             (0,4.125,7.3),(1,.325,1),(-5.6,4.125,-5),(-3,.325,-2),(0,.325,5.7),(5.5,4.125,4.8))


class CameraConflictError(RuntimeError):pass


def validate_document(document):
    result=validate_cameras(document)
    if result['scene']!='huxin_moon':raise CameraValidationError('scene: expected huxin_moon')
    for shot in result['shots']:
        active=shot['activation'];kind=active['type']
        if kind in ('lake','room') and active['index']>=(9 if kind=='lake' else 11):
            raise CameraValidationError(f"{shot['id']}: unknown {kind} camera index")
    return result


def default_document():
    shots=[]
    def append(identity,label,pose,kind,actor,phase,aim='fixed',index=None,duration=4.,offset=.95):
        eye,target,fov=pose;frame=dict(eye=list(eye),target=list(target),fov=float(fov))
        active={'type':kind,'priority':0}
        if index is not None:active['index']=index
        shots.append(dict(id=identity,label=label,enabled=True,activation=active,movement='locked',aim=aim,
                          lens='fixed',easing='smooth',duration=duration,start=frame,end=deepcopy(frame),
                          preview=dict(phase=phase,actor=list(actor),yaw=math.pi),aim_offset=[0.,offset,0.]))
    for i,(label,eye,target,fov) in enumerate(LAKE_SHOTS):
        append(f'lake-{i}',label,(eye,target,fov),'lake',LAKE_ACTORS[i],'lake','keep_visible',i,offset=.93)
    for i,(label,eye,target,fov) in enumerate(ROOM_SHOTS):
        append(f'room-{i}',label,(eye,target,fov),'room',ROOM_ACTORS[i],'teahouse','player',i,offset=.92)
    append('focus','The mirror',((2.85,3.6,2.4),(.35,1.16,-.05),57),'focus',(1.3,.325,1.3),'lake')
    append('reveal','The house takes shape',((18.,7.6,26.),(2.,4.5,0.),51),'reveal',(1.3,.325,1.3),'reveal',duration=24.)
    return validate_document(dict(version=1,scene='huxin_moon',shots=shots))


def _reject_constant(value):raise CameraValidationError('JSON contains a non-finite number: '+value)


def _unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise CameraValidationError('JSON contains duplicate key: '+key)
        result[key]=value
    return result


def _read(path):
    try:
        with Path(path).open('rb') as stream:raw=stream.read(MAX_BYTES+1)
    except FileNotFoundError:return default_document(),None
    if len(raw)>MAX_BYTES:raise CameraValidationError('Camera file exceeds 2 MB')
    try:data=json.loads(raw.decode('utf-8-sig'),parse_constant=_reject_constant,object_pairs_hook=_unique_object)
    except (ValueError,UnicodeError,RecursionError) as exc:raise CameraValidationError('Invalid camera JSON: '+str(exc)) from exc
    return validate_document(data),hashlib.sha256(raw).hexdigest()


def _fingerprint(path):
    try:
        with Path(path).open('rb') as stream:
            digest=hashlib.sha256()
            while True:
                block=stream.read(65536)
                if not block:break
                digest.update(block)
            return digest.hexdigest()
    except FileNotFoundError:return None


def _stamp(path):
    try:
        value=Path(path).stat();return value.st_mtime_ns,value.st_size
    except FileNotFoundError:return None


def load_document(path=DEFAULT_PATH):return _read(path)[0]


class CameraWatcher:
    """Read-only live reload; partial writes cannot replace a working camera rig."""
    def __init__(self,path=DEFAULT_PATH):
        self.path=Path(path);self.document=default_document();self.error=None;self.signature=None
        self._observed=object();self.poll(force=True)

    def poll(self,force=False):
        try:stamp=_stamp(self.path)
        except OSError as exc:self.error=str(exc);return False
        if not force and stamp==self._observed:return False
        self._observed=stamp
        try:document,signature=_read(self.path)
        except (OSError,ValueError,RecursionError) as exc:self.error=str(exc);return False
        changed=document!=self.document
        self.document=document;self.signature=signature;self.error=None
        return changed


class CameraDocument:
    """Editable camera document with grouped undo and conflict-aware persistence."""
    def __init__(self,path=DEFAULT_PATH,document=None):
        self.path=Path(path);watcher=CameraWatcher(self.path)
        self.saved=deepcopy(watcher.document)
        self.document=validate_document(document) if document is not None else deepcopy(self.saved)
        self._signature=watcher.signature;self._observed=watcher._observed
        self.error=watcher.error;self.conflict=bool(self.error)
        self.selected=self.document['shots'][0]['id'];self._key='start';self.elapsed=0.;self.playing=False;self.loop=False
        self._undo=[];self._redo=[]

    @property
    def dirty(self):return self.document!=self.saved
    @property
    def shot(self):return next(s for s in self.document['shots'] if s['id']==self.selected)
    @property
    def frame(self):return self.shot[self.key]
    @property
    def key(self):return self._key
    @key.setter
    def key(self,value):
        if value not in ('start','end'):raise ValueError('Camera key must be start or end')
        self._key=value;self.elapsed=0. if value=='start' else self.shot['duration'];self.playing=False
    @property
    def can_undo(self):return bool(self._undo)
    @property
    def can_redo(self):return bool(self._redo)

    def _entry(self,document=None):return deepcopy(self.document if document is None else document),self.selected,self.key,self.elapsed
    def _push(self,before):
        self._undo.append(before);self._undo=self._undo[-100:];self._redo.clear()
    def _restore(self,entry):
        document,selected,key,elapsed=entry;self.document=deepcopy(document)
        self.selected=selected if any(s['id']==selected for s in document['shots']) else document['shots'][0]['id']
        self._key=key;self.elapsed=min(max(0.,elapsed),self.shot['duration']);self.playing=False
    def checkpoint(self):return deepcopy(self.document)

    def commit(self,before):
        try:clean=validate_document(self.document)
        except (ValueError,TypeError,KeyError):
            self.document=deepcopy(before)
            if not any(s['id']==self.selected for s in self.document['shots']):self.selected=self.document['shots'][0]['id']
            raise
        changed=clean!=before
        if changed:self._push(self._entry(before))
        self.document=clean
        if not any(s['id']==self.selected for s in clean['shots']):self.selected=clean['shots'][0]['id']
        self.elapsed=min(self.elapsed,self.shot['duration'])
        return changed

    def change(self,operation):
        before=self.checkpoint()
        try:operation(self.shot);return self.commit(before)
        except Exception:
            self.document=before
            if not any(s['id']==self.selected for s in before['shots']):self.selected=before['shots'][0]['id']
            raise

    def set_frame(self,pose):return self.change(lambda shot:shot.__setitem__(self.key,deepcopy(pose)))
    def select(self,identity):
        if isinstance(identity,int) and not isinstance(identity,bool):identity=self.document['shots'][identity]['id']
        if not any(s['id']==identity for s in self.document['shots']):raise KeyError(identity)
        self.selected=identity;self.key='start'
        return self.shot
    def seek(self,elapsed):
        if isinstance(elapsed,bool) or not isinstance(elapsed,(int,float)) or not math.isfinite(elapsed):raise ValueError('Timeline time must be finite')
        self.elapsed=max(0.,min(float(elapsed),self.shot['duration']));self.playing=False
        return self.elapsed
    def tick(self,dt):
        if isinstance(dt,bool) or not isinstance(dt,(int,float)) or not math.isfinite(dt) or dt<0:raise ValueError('Timeline step must be nonnegative and finite')
        if self.playing:
            self.elapsed+=dt;duration=self.shot['duration']
            if self.elapsed>=duration:
                if self.loop:self.elapsed%=duration
                else:self.elapsed=duration;self.playing=False
        return self.elapsed
    def undo(self):
        if not self._undo:return False
        self._redo.append(self._entry());self._restore(self._undo.pop());return True
    def redo(self):
        if not self._redo:return False
        self._undo.append(self._entry());self._restore(self._redo.pop());return True

    def duplicate(self):
        before=self._entry();original=self.shot;clone=deepcopy(original);used={s['id'] for s in self.document['shots']}
        stem=original['id'][:65]+'-copy';identity=stem;n=2
        while identity in used:identity=f'{stem}-{n}';n+=1
        clone['id']=identity;clone['label']=original['label'][:95]+' copy'
        priority=original['activation']['priority'];clone['activation']['priority']=min(1000,priority+1)
        self.document['shots'].insert(self.document['shots'].index(original)+(0 if priority==1000 else 1),clone)
        try:self.document=validate_document(self.document)
        except ValueError:self._restore(before);raise
        self._push(before);self.select(identity);return self.shot
    def remove(self):
        if len(self.document['shots'])==1:raise ValueError('Keep at least one camera shot')
        before=self._entry();index=self.document['shots'].index(self.shot)
        self.document['shots'].pop(index);self._push(before)
        self.select(min(index,len(self.document['shots'])-1));return self.shot

    def save(self,force=False):
        clean=validate_document(self.document)
        if not force and _fingerprint(self.path)!=self._signature:
            self.conflict=True;self.error='Camera file changed outside the editor. Reload it or explicitly keep your edits.'
            raise CameraConflictError(self.error)
        payload=(json.dumps(clean,ensure_ascii=False,allow_nan=False,indent=2)+'\n').encode('utf-8')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary=None
        try:
            with tempfile.NamedTemporaryFile(mode='wb',prefix='.'+self.path.name+'.',suffix='.tmp',dir=self.path.parent,delete=False) as stream:
                temporary=Path(stream.name);stream.write(payload);stream.flush();os.fsync(stream.fileno())
            if not force and _fingerprint(self.path)!=self._signature:
                self.conflict=True;self.error='Camera file changed while saving; your edits were not written.'
                raise CameraConflictError(self.error)
            os.replace(temporary,self.path);temporary=None
        finally:
            if temporary is not None:
                try:temporary.unlink()
                except FileNotFoundError:pass
        self.document=clean;self.saved=deepcopy(clean);self._signature=hashlib.sha256(payload).hexdigest()
        self._observed=_stamp(self.path);self.error=None;self.conflict=False
        return self.path

    def reload(self):
        try:document,signature=_read(self.path)
        except (OSError,ValueError) as exc:self.error=str(exc);raise
        before=self._entry();playing=self.playing
        if document!=self.document:self._push(before)
        self._restore((document,self.selected,self.key,self.elapsed));self.playing=playing
        self.saved=deepcopy(document);self._signature=signature;self._observed=_stamp(self.path)
        self.error=None;self.conflict=False
        return self.document

    def discard(self):
        before=self._entry()
        if self.document!=self.saved:self._push(before)
        self._restore((self.saved,self.selected,self.key,self.elapsed))
        return self.document

    def poll(self,force=False):
        """Clean edits reload in place; dirty edits hold and report a conflict."""
        try:stamp=_stamp(self.path)
        except OSError as exc:self.error=str(exc);return False
        if not force and stamp==self._observed:return False
        self._observed=stamp
        try:document,signature=_read(self.path)
        except (OSError,ValueError) as exc:self.error=str(exc);return False
        if signature==self._signature:
            self.error=None;self.conflict=False;return False
        if self.dirty:
            self.conflict=True;self.error='Camera file changed outside the editor. Reload it or explicitly keep your edits.'
            return False
        before=self.document;selected=self.selected;key=self.key;elapsed=self.elapsed;playing=self.playing
        self._restore((document,selected,key,elapsed));self.playing=playing
        self.saved=deepcopy(document);self._signature=signature;self.error=None;self.conflict=False
        self._undo.clear();self._redo.clear()
        return document!=before


class DirectionEditor(CameraDocument):
    def __init__(self,document=None,path=DEFAULT_PATH):super().__init__(path=path,document=document)
