"""Settings saved in .blend files; do not postpone annotations because RNA needs property instances."""
import bpy
from bpy.props import EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty


# Newer Blender versions require explicit support for // paths; older ones
# support them implicitly and do not recognize the new option.
_PATH_OPTIONS = {'ANIMATABLE'}
if "is_path_supports_blend_relative" in bpy.types.Property.bl_rna.properties:
    _PATH_OPTIONS.add('PATH_SUPPORTS_BLEND_RELATIVE')


def mesh_object(_self, obj):
    return obj.type == 'MESH'


class SIMFORGE_PG_settings(bpy.types.PropertyGroup):
    high_poly: PointerProperty(name="High Poly", type=bpy.types.Object, poll=mesh_object)
    low_poly: PointerProperty(name="Low Poly", type=bpy.types.Object, poll=mesh_object)
    target_faces: IntProperty(name="Target Faces", default=10000, min=100)
    voxel_size: FloatProperty(name="Voxel Size", default=0.005, min=0.0001, max=1, subtype="DISTANCE")
    smart_uv_angle: FloatProperty(name="Smart UV Angle", subtype='ANGLE',
                                  default=1.1519173063, min=0.01, max=1.5707963268)
    uv_margin: FloatProperty(name="UV Margin", default=0.001, min=0.0, max=0.25)
    resolution: EnumProperty(name="Texture Size", items=[
        (str(size), str(size), "") for size in (512, 1024, 2048, 4096, 8192)
    ], default='2048')
    cage_extrusion: FloatProperty(name="Cage Extrusion", default=0.01, min=0.0,
                                  subtype='DISTANCE')
    texture_directory: StringProperty(name="Texture Directory", subtype='DIR_PATH',
                                      default="//simforge_textures/", options=_PATH_OPTIONS)
    export_path: StringProperty(name="USD File", subtype='FILE_PATH',
                               default="//asset.usdc", options=_PATH_OPTIONS)
    body_type: EnumProperty(name="Body Type", items=[
        ('DYNAMIC', "Dynamic", "A dynamic rigid body"), ('STATIC', "Static", "A static collider")
    ], default='DYNAMIC')
    mass_kg: FloatProperty(name="Mass (kg)", default=1.0, min=0.0001)
    collision_approximation: EnumProperty(name="Collision", items=[
        ('convexHull', "Convex Hull", "Convex hull"),
        ('convexDecomposition', "Convex Decomposition", "Convex decomposition")
    ], default='convexHull')
    static_friction: FloatProperty(name="Static Friction", default=0.5, min=0.0)
    dynamic_friction: FloatProperty(name="Dynamic Friction", default=0.5, min=0.0)
    restitution: FloatProperty(name="Restitution", default=0.0, min=0.0, max=1.0)
