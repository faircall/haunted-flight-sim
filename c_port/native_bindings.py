"""Skip Python's generic pyray adapter when the signature needs no conversion.

Calls still go to the installed raylib/CFFI library so there is exactly one
graphics context. Pointer and string adapters retain the upstream ownership
rules. This is installed only by the C game's entry point.
"""
import pyray as pr


def install():
    count = 0
    for name in dir(pr.rl):
        function = getattr(pr.rl, name)
        try:
            signature = pr.ffi.typeof(function)
        except TypeError:
            continue
        if signature.kind != 'function' or signature.ellipsis:
            continue
        if signature.result.kind == 'pointer' or any(arg.kind == 'pointer' for arg in signature.args):
            continue
        pyname = pr._underscore(name).replace('3_d', '_3d').replace('2_d', '_2d')
        if hasattr(pr, pyname):
            setattr(pr, pyname, function)
            count += 1

    # These types contain values only: the returned CFFI object owns its data.
    # Pointer-bearing structs keep pyray's retained-buffer/weak-reference path.
    for name in ('Vector2', 'Vector3', 'Vector4', 'Quaternion', 'Matrix', 'Color',
                 'Rectangle', 'Texture', 'Texture2D', 'RenderTexture', 'RenderTexture2D',
                 'Camera2D', 'Camera3D', 'Ray', 'BoundingBox'):
        if not hasattr(pr, name):
            continue
        pointer_type = pr.ffi.typeof(name + ' *')
        field_count = len(pointer_type.item.fields)
        def construct(*values, _type=pointer_type, _count=field_count):
            return pr.ffi.new(_type, values[:_count])[0]
        setattr(pr, name, construct)
    return count
