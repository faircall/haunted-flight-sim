"""Play with the Chorus figure in an isolated Moon-lake chase study.

This is an animation trial, not a change to the shipped enemy or encounter.
"""
if __name__=='__main__':
    from setup_temple_3d import ensure_runtime
    ensure_runtime()

import math
import pyray as pr
from g_chorus_trial import FigureMotion
from g_huxin_moon import Explorer,PLAYER_SCALE,walk_height
from g_huxin_moon_sequence import causeway_point
from g_temple_living import LivingScene
from huxin_moon_viewer import Lake,PLAYER_UNIFORMS,WIDTH,HEIGHT,reset_player
from temple_interior_viewer import camera


class ChorusTrialScene(Lake):
    def __init__(self):
        self.figure=None;self.motion=FigureMotion();self.figure_dt=1/60
        super().__init__()
        try:
            self.figure=LivingScene(include_willow=False,actor='chorus_grasper',fragment_shader='huxin_moon.fs')
            self.locations[self.figure.skin.id]={name:pr.get_shader_location(self.figure.skin,name) for name in PLAYER_UNIFORMS}
        except Exception:
            self.close();raise

    def environment(self,cam,clock,inspection,reflection):
        super().environment(cam,clock,inspection,reflection)
        if self.figure is not None:
            # Give the independent figure exactly the same fog, lamp and moon
            # uniforms as the player, including the reflected geometry pass.
            old=self.player;self.player=self.figure
            try:super().environment(cam,clock,inspection,reflection)
            finally:self.player=old

    def geometry(self,e,cam,clock,reflection,show_player):
        super().geometry(e,cam,clock,reflection,show_player)
        if self.figure is None:return
        x,y,z=self.motion.position
        if not reflection:
            pr.draw_cylinder_ex(pr.Vector3(x,y+.012,z),pr.Vector3(x,y+.014,z),.26,.26,24,pr.Color(3,9,10,95))
        scale=pr.Vector3(PLAYER_SCALE,-PLAYER_SCALE if reflection else PLAYER_SCALE,PLAYER_SCALE)
        pr.draw_model_ex(self.figure.player,pr.Vector3(x,-y-.01 if reflection else y+.01,z),
                         pr.Vector3(0,1,0),180-math.degrees(self.motion.yaw),scale,pr.WHITE)

    def render(self,e,clock,inspection=False,override=None,show_player=True,assembly=False,authoring=False,manual_shot=None):
        self.figure.pose(self.motion.clip,self.motion.pose_phase,self.figure_dt)
        return super().render(e,clock,inspection,override,show_player,assembly,authoring,manual_shot)

    def close(self):
        if self.figure is not None:self.figure.close();self.figure=None
        super().close()


def reset_trial(scene):
    actor=reset_player(scene);actor.x,actor.z=causeway_point(.78)
    actor.height=walk_height(actor.x,actor.z);actor.yaw=0.;actor.tick(0.)
    scene.motion=FigureMotion()
    return actor


def orbit_camera(actor,figure,angle,zoom):
    fx,fy,fz=figure.position
    cx,cz=(actor.x+fx)/2.,(actor.z+fz)/2.
    gap=math.hypot(actor.x-fx,actor.z-fz)
    distance=max(3.5,min(20.,5.+gap*.52+zoom))
    return camera((cx+math.sin(angle)*distance,max(actor.height,fy)+1.7+distance*.19,cz+math.cos(angle)*distance),
                  (cx,max(actor.height,fy)+.92,cz),55)


def run():
    pr.set_trace_log_level(pr.LOG_WARNING);pr.init_window(1280,720,'The Chorus / Causeway study');pr.set_target_fps(60)
    scene=None
    try:
        scene=ChorusTrialScene();actor=reset_trial(scene)
        clock=0.;angle=math.pi/2;zoom=0.;inspection=False;show_help=True;notice='';notice_until=0.
        while not pr.window_should_close():
            dt=min(.05,pr.get_frame_time());clock+=dt
            for key,mode in ((pr.KEY_ONE,'idle'),(pr.KEY_TWO,'walk'),(pr.KEY_THREE,'brisk'),(pr.KEY_FOUR,'follow')):
                if pr.is_key_pressed(key):scene.motion.mode=mode
            if pr.is_key_pressed(pr.KEY_SPACE):scene.motion.paused=not scene.motion.paused
            if pr.is_key_pressed(pr.KEY_R):actor=reset_trial(scene)
            if pr.is_key_pressed(pr.KEY_L):inspection=not inspection
            if pr.is_key_pressed(pr.KEY_H):show_help=not show_help
            if pr.is_key_pressed(pr.KEY_F4):
                clip=actor.clip if actor.clip in scene.player.clips else 'idle'
                phase=actor.phase if clip in ('walk','run','walk_back') else clock if clip.startswith('turn') else clock/2.
                selected='refined' if scene.player.variant=='original' else 'original'
                try:scene.set_player_variant(selected,clip,phase);notice='Player: '+selected.title()
                except (OSError,RuntimeError,ValueError) as exc:notice='Player switch failed: '+str(exc)
                notice_until=clock+3.
            if pr.is_mouse_button_down(pr.MOUSE_BUTTON_RIGHT):angle-=pr.get_mouse_delta().x*.006
            zoom=max(-4.,min(12.,zoom-pr.get_mouse_wheel_move()*.7))
            forward=int(pr.is_key_down(pr.KEY_W))-int(pr.is_key_down(pr.KEY_S))
            turn=int(pr.is_key_down(pr.KEY_D))-int(pr.is_key_down(pr.KEY_A))
            actor.tick(dt,forward,turn,pr.is_key_down(pr.KEY_LEFT_SHIFT))
            scene.sequence.tick(dt,actor);scene.motion.tick(dt,actor);scene.figure_dt=0. if scene.motion.paused else dt
            view=orbit_camera(actor,scene.motion,angle,zoom)
            scene.render(actor,clock,inspection,override=view,authoring=True)
            pr.begin_drawing();pr.clear_background(pr.BLACK)
            pr.draw_texture_pro(scene.frame.texture,pr.Rectangle(0,0,WIDTH,-HEIGHT),pr.Rectangle(0,0,1280,720),pr.Vector2(0,0),0,pr.WHITE)
            label={'follow':'FOLLOW PLAYER','idle':'IDLE IN PLACE','walk':'WALK IN PLACE','brisk':'BRISK WALK IN PLACE'}[scene.motion.mode]
            if scene.motion.paused:label+=' / PAUSED'
            pr.draw_rectangle(0,0,1280,36,pr.Color(10,20,22,200));pr.draw_text('CHORUS FIGURE / '+label,18,10,18,pr.Color(223,223,202,255))
            if clock<notice_until:pr.draw_text(notice,860,11,16,pr.Color(225,218,183,255))
            if show_help:
                pr.draw_rectangle(0,651,1280,69,pr.Color(10,20,22,226))
                pr.draw_text('W/S move  |  A/D turn  |  Shift run  |  1 idle  2 walk  3 brisk walk  4 follow',18,660,16,pr.Color(206,213,198,255))
                pr.draw_text('Right-drag orbit  |  wheel zoom  |  Space pause figure  |  R reset  |  L light  |  F4 player  |  H help',18,684,14,pr.Color(147,178,175,255))
                pr.draw_text('Animation study: the figure does not damage the player.',850,705,12,pr.Color(147,178,175,255))
            pr.end_drawing()
    finally:
        if scene:scene.close()
        pr.close_window()


if __name__=='__main__':run()
