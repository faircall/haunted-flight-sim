"""Native camera aiming, GPU enemy poses and brief combat feedback."""
import math
import pyray as pr
from g_temple_combat import world,ENEMY_AIM_HEIGHT
from g_temple_editor import ground_point, gameplay_camera
from g_temple_living import LivingScene
import g_temple_structure as structure


def aim_point(gameplay,camera,screen):
    tm=gameplay.arena['tile_map']
    # A small screen-space body target makes a tall actor aimable in an
    # orthographic shot; the subsequent 3D trace still checks walls and height.
    candidates=[]
    for identity,actor in gameplay.combat.actors.items():
        if actor['health']<=0:continue
        x,z=world(actor,tm);h=structure.floor_height(tm,x,z)+ENEMY_AIM_HEIGHT
        p=pr.get_world_to_screen_ex(pr.Vector3(x,h,z),camera,480,270)
        distance=math.hypot(screen[0]-p.x,screen[1]-p.y)
        if distance<=12:candidates.append((distance,identity,(x,h,z)))
    if candidates:return min(candidates)[2]
    values=lambda v:(v.x,v.y,v.z)
    levels=tuple(h+18.5 for h in tm.get('temple3d_levels',(0,16,24)))
    p=ground_point(values(camera.position),values(camera.target),values(camera.up),camera.fovy,
        screen,lambda x,z:structure.floor_height(tm,x,z)+18.5,levels)
    return (p[0],structure.floor_height(tm,*p)+18.5,p[1]) if p else None


def controls(gameplay):
    mouse=pr.get_mouse_position();inside=0<=mouse.x<1440 and 0<=mouse.y<810
    aiming=inside and pr.is_mouse_button_down(pr.MOUSE_BUTTON_RIGHT)
    return dict(aiming=aiming,aim=aim_point(gameplay,gameplay_camera(gameplay),(mouse.x/3,mouse.y/3)) if aiming else None,
        fire=inside and pr.is_mouse_button_pressed(pr.MOUSE_BUTTON_LEFT),reload=pr.is_key_pressed(pr.KEY_T))


class CombatView:
    def __init__(self):self.enemies={}

    def update(self,gameplay,player,dt,inspection,lights):
        combat=gameplay.combat
        if player:
            if not gameplay.paused:
                player.yaw=math.degrees(math.atan2(*gameplay.walk.facing))
            if combat.dead:
                player.pose('death',min(.999,combat.death_time/.9),dt)
            elif not gameplay.paused and combat.hurt_time:
                player.pose('hurt',min(.999,1-combat.hurt_time/.3),dt)
            elif not gameplay.paused and combat.reload:
                player.pose('reload',min(.999,1-combat.reload/1.15),dt)
            elif not gameplay.paused and (combat.aiming or combat.reload):
                player.yaw=math.degrees(math.atan2(*combat.heading))
                if combat.recoil:
                    player.pose('recoil',min(.999,1-combat.recoil/.18),dt)
                else:
                    clip='aim'
                    if gameplay.walk.moving:
                        fx,fz=combat.heading;dx,dz=gameplay.walk.heading
                        forward=fx*dx+fz*dz;right=fz*dx-fx*dz
                        clip=('aim_walk' if forward>=0 else 'aim_back') if abs(forward)>=abs(right) else ('aim_right' if right>=0 else 'aim_left')
                    player.pose(clip,player.phase if gameplay.walk.moving else 0.,dt)
            elif not gameplay.paused:
                walk=gameplay.walk
                if walk.moving:
                    clip='walk_back' if walk.backwards else 'run' if walk.running else 'walk'
                    player.pose(clip,player.phase,dt)
                elif walk.turning:
                    player.pose('turn_right' if walk.turning>0 else 'turn_left',walk.turn_distance/120.,dt)
                else:player.pose('idle',gameplay.clock/2.,dt)
        tm=gameplay.arena['tile_map']
        for identity in list(self.enemies):
            if identity not in combat.actors:self.enemies.pop(identity).close()
        for identity,actor in combat.actors.items():
            if identity not in self.enemies:self.enemies[identity]=LivingScene(False,actor='redhead')
            model=self.enemies[identity];model.environment(gameplay.clock,inspection,lights)
            state=actor['current_state']
            if not gameplay.paused:
                model.phase+=actor.get('travelled',0)/14.
                if state=='dead':clip,phase='enemy_death',min(.999,actor.get('death_timer',0)/.9)
                elif state=='stagger':clip,phase='enemy_stagger',min(.999,actor.get('stagger_timer',0)/.35)
                elif state=='angry and attacking':
                    clip='enemy_attack'
                    phase=min(.6,actor.get('attack_timer',0)/actor['attack_windup_duration']*.6)
                    if actor.get('attack_substate')=='attacking':phase=min(.999,.6+actor.get('attack_timer',0)/.35*.4)
                else:clip,phase=('enemy_walk',model.phase) if actor.get('travelled',0)>.001 else ('enemy_idle',gameplay.clock/2)
                model.pose(clip,phase,dt)
                heading=actor.get('attack_direction') if state=='angry and attacking' else None
                heading=heading or dict(zip(('x','y'),actor.get('heading',(0,1))))
                goal=math.degrees(math.atan2(heading['x'],heading['y']))
                model.yaw+=((goal-model.yaw+180)%360-180)*min(1,dt*12)

    def draw(self,gameplay,player,player_floor):
        c=gameplay.combat;tm=gameplay.arena['tile_map']
        for identity,model in self.enemies.items():
            actor=c.actors[identity];x,z=world(actor,tm)
            model.draw_player(x,structure.floor_height(tm,x,z),z)
        if player and not c.dead and (c.aiming or c.reload):player.draw_pistol(gameplay.walk.x,player_floor,gameplay.walk.y)
        for trail in c.trails:
            a,b=trail['start'],trail['end']
            pr.draw_line_3d(pr.Vector3(*a),pr.Vector3(*b),pr.Color(244,214,131,255))
            pr.draw_sphere(pr.Vector3(*a),.6,pr.Color(255,217,122,255))
            if trail['hit']:pr.draw_sphere(pr.Vector3(*b),.7,pr.Color(153,58,46,255))

    def draw_ui(self,gameplay):
        c=gameplay.combat
        if c.hurt_time:pr.draw_rectangle_lines(2,2,476,266,pr.Color(195,65,55,255))
        if c.dead:
            pr.draw_rectangle(95,105,290,60,pr.Color(7,12,20,235))
            pr.draw_text('YOU DIED',188,116,16,pr.Color(220,194,159,255))
            pr.draw_text('Enter: restart  |  F6: load save',116,144,10,pr.RAYWHITE)
        elif c.aiming:
            mouse=pr.get_mouse_position();x,y=int(mouse.x/3),int(mouse.y/3)
            color=pr.Color(241,212,144,255)
            pr.draw_line(x-5,y,x-2,y,color);pr.draw_line(x+2,y,x+5,y,color)
            pr.draw_line(x,y-5,x,y-2,color);pr.draw_line(x,y+2,x,y+5,color)
        ammo=gameplay.player['ammo']
        pr.draw_text(f"PISTOL {ammo.get('pistol',0)} / {ammo.get('spare_pistol',0)}",354,14,10,pr.Color(210,203,177,255))
        if c.reload:pr.draw_text('RELOADING',370,30,10,pr.YELLOW)

    def close(self):
        for model in self.enemies.values():model.close()
        self.enemies.clear()
