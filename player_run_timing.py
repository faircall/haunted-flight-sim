"""A small timing revision to the accepted player run's airborne leg.

The standing foot, stride distance, upper body and contact poses stay on the
existing authored gait. The airborne thigh keeps moving through rear recovery
and turns around more briskly at the front of the stride.
"""
import math
from contextlib import contextmanager

from photo_asset_pipeline.temple3d.living import gait

TURN_SHARPNESS = .20
PASSING_PHASE = .565
DRIVE_PHASE = gait.SETTINGS['run']['knee_drive']
_accepted_swing_angles = gait._run_swing_angles


def swing_angles(phase):
    """Return accepted angles with less time lingering at either stride end."""
    thigh, flex = _accepted_swing_angles(phase)
    stance = gait.SETTINGS['run']['stance']
    if stance < phase < .48:
        # Keep the same contact, exit pose and tangents. A slightly deeper
        # early recovery gives the thigh room to advance through the rear arc
        # instead of almost stopping around phase .44.
        if phase < .38:
            initial = gait._run_contact_angles(stance)
            before = gait._run_contact_angles(stance-1e-6)
            rate = (initial[0]-before[0])/1e-6
            thigh = gait.hermite(initial[0], math.radians(-19.), rate,
                                 math.radians(150.), (phase-stance)/(.38-stance), .38-stance)
        else:
            thigh = gait.hermite(math.radians(-19.), math.radians(-8.),
                                 math.radians(150.), math.radians(120.),
                                 (phase-.38)/.10, .10)
    if phase < PASSING_PHASE:
        return thigh, flex
    landing = gait._run_contact_angles(0.)
    after = gait._run_contact_angles(1e-6)
    landing_rate = (after[0] - landing[0]) / 1e-6
    flex_landing_rate = (after[1]-landing[1]) / 1e-6
    peak = gait.SETTINGS['run']['recovery_peak']
    maximum = math.radians(gait.SETTINGS['run']['recovery_bend'])
    front = maximum-math.radians(9.)
    # Begin opening a little more decisively as the thigh reaches the front.
    # Both segments have the same tangent at the join and retain the exact
    # landing bend/velocity; the knee continues opening rather than refolding.
    if peak <= phase < DRIVE_PHASE:
        flex = gait.hermite(maximum, front, 0., math.radians(-120.),
                            (phase-peak)/(DRIVE_PHASE-peak), DRIVE_PHASE-peak)
    elif phase >= DRIVE_PHASE:
        flex = gait.hermite(front, landing[1], math.radians(-120.), flex_landing_rate,
                            (phase-DRIVE_PHASE)/(1-DRIVE_PHASE), 1-DRIVE_PHASE)
    if phase < DRIVE_PHASE:
        t = (phase - PASSING_PHASE) / (DRIVE_PHASE - PASSING_PHASE)
        # Same velocity at the passing pose, greater curvature at the peak.
        t -= TURN_SHARPNESS * t*t*(1-t)
        thigh = gait.hermite(math.radians(2.), math.radians(80.),
                             math.radians(120.), 0., t, DRIVE_PHASE-PASSING_PHASE)
    else:
        t = (phase - DRIVE_PHASE) / (1 - DRIVE_PHASE)
        # Leave the peak sooner; preserve the landing velocity and pose.
        t += TURN_SHARPNESS * t*(1-t)*(1-t)
        thigh = gait.hermite(math.radians(80.), landing[0], 0., landing_rate,
                             t, 1-DRIVE_PHASE)
    thigh -= math.radians(40.) * t*t*(1-t)**2
    return thigh, flex


@contextmanager
def timing_revision():
    """Temporarily substitute only the leg curve while baking or inspecting."""
    original = gait._run_swing_angles
    gait._run_swing_angles = swing_angles
    try:
        yield
    finally:
        gait._run_swing_angles = original
