"""Retarget shared motion onto a player with different arm lengths."""


def arm_positions(shoulder, elbow, wrist, upper_scale, forearm_scale):
    new_elbow=tuple(s+upper_scale*(e-s) for s,e in zip(shoulder,elbow))
    new_wrist=tuple(e+forearm_scale*(w-old_e) for e,w,old_e in zip(new_elbow,wrist,elbow))
    return new_elbow,new_wrist
