"""Rainy car intro, then the temple. Use --skip-intro for direct gameplay."""
if __name__=='__main__':
    from setup_temple_3d import ensure_runtime
    ensure_runtime()
    from temple_3d_viewer import run
    run(fixed_cameras=True,living_assets=True)
