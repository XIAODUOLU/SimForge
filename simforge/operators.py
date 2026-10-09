"""Thin Operators with shared error handling; services hold algorithms and workflow validates inputs."""
import logging

import bpy

from . import workflow
from .core.errors import FeatureNotImplemented, SimForgeError

logger = logging.getLogger(__name__)


class OperationMixin:
    @classmethod
    def poll(cls, context):
        return context.scene is not None and context.mode == 'OBJECT'

    def execute(self, context):
        try:
            self.run(context)
        except FeatureNotImplemented as exc:
            self.report({'WARNING'}, str(exc))
            return {'CANCELLED'}
        except SimForgeError as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        except Exception:
            logger.exception("SimForge operation failed: %s", self.bl_idname)
            self.report({'ERROR'}, "Operation failed. See the SimForge traceback in the system console.")
            return {'CANCELLED'}
        self.report({'INFO'}, "SimForge operation completed.")
        return {'FINISHED'}


class SIMFORGE_OT_retopo(OperationMixin, bpy.types.Operator):
    bl_idname = "simforge.retopo"
    bl_label = "Retopo"
    bl_description = "Create a low-poly mesh, then run Smart UV Project and Pack Islands"
    bl_options = {'REGISTER', 'UNDO'}
    run = staticmethod(workflow.run_retopo)


class SIMFORGE_OT_bake(OperationMixin, bpy.types.Operator):
    bl_idname = "simforge.bake"
    bl_label = "Bake"
    bl_description = "Bake Normal and Base Color"
    bl_options = {'REGISTER', 'UNDO'}
    run = staticmethod(workflow.run_bake)


class SIMFORGE_OT_export(OperationMixin, bpy.types.Operator):
    bl_idname = "simforge.export"
    bl_label = "Export"
    bl_description = "Export Isaac Sim USD with collision and physics attributes"
    # File writes cannot be undone; do not declare UNDO.
    bl_options = {'REGISTER'}
    run = staticmethod(workflow.run_export)
