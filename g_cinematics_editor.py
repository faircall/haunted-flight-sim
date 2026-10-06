"""Cinematics authoring state: transactions, camera keys, cuts and atomic saves."""
from copy import deepcopy
import json
import os
from pathlib import Path
from g_temple_intro import SCRIPT,load_script,validate_script
from g_temple_cinematics import default_camera,sample_camera,validate_camera


class Cinematics:
    def __init__(self,document=None,path=SCRIPT):
        self.path=Path(path);self.document=deepcopy(document if document is not None else load_script(path))
        validate_script(self.document)
        for shot in self.document['shots']:shot.setdefault('camera',default_camera(shot['kind']))
        self.saved=deepcopy(self.document);self.undo_stack=[];self.redo_stack=[]
        self.selected=0;self.key='start';self.elapsed=3.7;self.playing=False;self.loop=False

    @property
    def shot(self):return self.document['shots'][self.selected]

    @property
    def frame(self):return self.shot['camera'][self.key]

    @property
    def dirty(self):return self.document!=self.saved

    def checkpoint(self):return deepcopy(self.document)

    def history(self,document):return dict(document=document,selected=self.selected,key=self.key)

    def commit(self,before):
        try:validate_script(self.document)
        except (ValueError,KeyError,TypeError):self.document=before;raise
        if before!=self.document:
            self.undo_stack.append(self.history(before));self.undo_stack=self.undo_stack[-100:];self.redo_stack.clear();return True
        return False

    def change(self,operation):
        before=self.checkpoint()
        try:operation();return self.commit(before)
        except Exception:self.document=before;raise

    def undo(self):
        if not self.undo_stack:return False
        self.redo_stack.append(self.history(self.checkpoint()));self.restore(self.undo_stack.pop());return True

    def redo(self):
        if not self.redo_stack:return False
        self.undo_stack.append(self.history(self.checkpoint()));self.restore(self.redo_stack.pop());return True

    def restore(self,record):
        self.document=record['document'];self.selected=min(record['selected'],len(self.document['shots'])-1);self.key=record['key']

    def save(self):
        validate_script(self.document)
        temporary=self.path.with_suffix(self.path.suffix+'.tmp')
        try:
            temporary.write_text(json.dumps(self.document,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
            os.replace(temporary,self.path)
        finally:
            if temporary.exists():temporary.unlink()
        self.saved=self.checkpoint()

    def reload(self):
        document=load_script(self.path)
        for shot in document['shots']:shot.setdefault('camera',default_camera(shot['kind']))
        before=self.checkpoint();self.document=document;self.commit(before);self.saved=deepcopy(document)
        self.selected=min(self.selected,len(document['shots'])-1)

    def select(self,index,key='start'):
        self.selected=max(0,min(len(self.document['shots'])-1,index));self.key=key;self.playing=False
        self.elapsed=self.shot[key] if key=='start' else self.shot['end']-1e-5

    def seek(self,elapsed):
        self.elapsed=max(0,min(self.document['duration']-1e-5,elapsed));self.playing=False
        self.selected=next(i for i,s in enumerate(self.document['shots']) if s['start']<=self.elapsed<s['end'])

    def tick(self,dt):
        if not self.playing:return
        end=self.shot['end'] if self.loop else self.document['duration']
        self.elapsed+=max(0,min(.1,dt))
        if self.elapsed>=end:
            if self.loop:self.elapsed=self.shot['start']+(self.elapsed-end)
            else:self.elapsed=end-1e-5;self.playing=False
        if not self.loop:self.selected=next(i for i,s in enumerate(self.document['shots']) if s['start']<=self.elapsed<s['end'])

    def set_frame(self,frame):
        def apply():self.shot['camera'][self.key]=deepcopy(frame)
        return self.change(apply)

    def match_keys(self):return self.change(lambda:self.shot['camera'].__setitem__('end' if self.key=='start' else 'start',deepcopy(self.frame)))

    def reset_camera(self):return self.change(lambda:self.shot.__setitem__('camera',default_camera(self.shot['kind'])))

    def cut_time(self,index,time):
        shots=self.document['shots']
        if not 1<=index<len(shots):raise ValueError('The first and last times are fixed.')
        minimum=min(1,(shots[index]['end']-shots[index-1]['start'])/3)
        return round(max(shots[index-1]['start']+minimum,min(shots[index]['end']-minimum,time)),4)

    def set_cut(self,index,time):
        shots=self.document['shots'];time=self.cut_time(index,time)
        def apply():shots[index-1]['end']=time;shots[index]['start']=time
        return self.change(apply)

    def split(self):
        original=self.shot
        if original['kind']=='tracking':raise ValueError('Move this shot\'s cut points to change the night transition.')
        time=round(self.elapsed,2)
        if not original['start']+1<=time<=original['end']-1:raise ValueError('Leave at least one second on each side of the new cut.')
        frame=sample_camera(original,time);second=deepcopy(original)
        names={s['id'] for s in self.document['shots']};base=original['id']+'-cut';name=base;n=2
        while name in names:name=base+'-'+str(n);n+=1
        second['id']=name;second['start']=time;second['camera']['start']=deepcopy(frame)
        def apply():
            original['end']=time;original['camera']['end']=deepcopy(frame)
            self.document['shots'].insert(self.selected+1,second)
        self.change(apply);self.selected+=1;self.key='start'

    def remove(self):
        if self.shot['kind']=='tracking':raise ValueError('Keep the night-transition shot; its camera and timing can be changed.')
        if len(self.document['shots'])<2:raise ValueError('Keep at least one shot.')
        index=self.selected
        def apply():
            removed=self.document['shots'].pop(index)
            if index:self.document['shots'][index-1]['end']=removed['end']
            else:self.document['shots'][0]['start']=0
        self.change(apply);self.selected=max(0,index-1);self.seek(self.shot['start'])
