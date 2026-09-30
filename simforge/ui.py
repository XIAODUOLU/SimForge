"""3D View sidebar; derive workflow state from objects and files instead of stale success flags."""
import bpy


class SIMFORGE_PT_main(bpy.types.Panel):
    bl_label = "SimForge"
    bl_idname = "SIMFORGE_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "SimForge"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.simforge
        layout.label(text="Development scaffold: implement services", icon='INFO')
        layout.prop(settings, "high_poly")
        layout.prop(settings, "low_poly")
        if context.mode != 'OBJECT':
            layout.label(text="Switch to Object Mode", icon='INFO')

        box = layout.box()
        box.label(text="1. Retopology & UV")
        for name in ("target_faces", "voxel_ratio", "smart_uv_angle", "uv_margin"):
            box.prop(settings, name)
        box.operator("simforge.retopo")

        box = layout.box()
        box.label(text="2. PBR Baking")
        box.label(text="Normal / Base Color / Metallic / Roughness / Alpha")
        for name in ("resolution", "margin_pixels", "cage_extrusion", "texture_directory"):
            box.prop(settings, name)
        box.operator("simforge.bake")

        box = layout.box()
        box.label(text="3. Isaac Sim USD")
        for name in ("export_path", "body_type", "collision_approximation"):
            box.prop(settings, name)
        row = box.row()
        row.enabled = settings.body_type == 'DYNAMIC'
        row.prop(settings, "mass_kg")
        for name in ("static_friction", "dynamic_friction", "restitution"):
            box.prop(settings, name)
        box.operator("simforge.export")
