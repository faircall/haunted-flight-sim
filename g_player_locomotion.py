"""Runtime stride lengths for the player, independent of the original authoring curves."""
from photo_asset_pipeline.temple3d.living.gait import SETTINGS as ORIGINAL_SETTINGS
from player_jog import JOG_STRIDE

SETTINGS = {name: dict(values) for name, values in ORIGINAL_SETTINGS.items()}
SETTINGS['run']['stride'] = JOG_STRIDE


def stride_for(clip, run_style='jog'):
    """Stride in model units; run retains its existing gameplay speed."""
    if clip == 'run' and run_style in ('sprint', 'legacy'):
        return ORIGINAL_SETTINGS['run']['stride']
    return SETTINGS['walk' if clip == 'walk_back' else clip]['stride']
