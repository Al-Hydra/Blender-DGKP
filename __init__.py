bl_info = {
    "name": "DGKP Importer/Exporter",
    "author": "HydraBladeZ",
    "description": "Import Kill la Kill model, texture and animation files into blender",
    "blender": (4, 2, 0),
    "version": (1, 2, 0),
    "location": "View3D",
    "warning": "",
    "category": "Import"
}

import bpy
import json
import os

from .dgkp_importer import *
from .dgkp_exporter import *

# -- JSON SETTINGS FILE HELPERS --

def get_settings_path():
    addon_dir = os.path.dirname(__file__)
    return os.path.join(addon_dir, "dgkp_settings.json")

def save_preferences_to_file(materials_path, enable_logging):
    path = get_settings_path()
    data = {
        "materials_path": materials_path,
        "enable_verbose_logging": enable_logging
    }
    with open(path, 'w') as f:
        json.dump(data, f, indent=4)

def load_preferences_from_file():
    path = get_settings_path()
    if not os.path.exists(path):
        return {"materials_path": "", "enable_verbose_logging": False}
    with open(path, 'r') as f:
        return json.load(f)

# -- ADDON PREFERENCES PANEL --

class DGKPAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    materials_path: bpy.props.StringProperty(
        name="Material Package Path",
        subtype='FILE_PATH',
        default="",
        description="Path to material_package.pac file"
    )

    enable_verbose_logging: bpy.props.BoolProperty(
        name="Enable Verbose Logging",
        default=False,
        description="Print detailed logs during import/export"
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text="DGKP Importer/Exporter Preferences")
        layout.prop(self, "materials_path")
        layout.prop(self, "enable_verbose_logging")

        row = layout.row()
        row.operator("dgkp.save_settings", icon="FILE_TICK")

# -- OPERATORS --

class DGKP_OT_SaveSettings(bpy.types.Operator):
    bl_idname = "dgkp.save_settings"
    bl_label = "Save to File"

    def execute(self, context):
        prefs = context.preferences.addons[__name__].preferences
        save_preferences_to_file(prefs.materials_path, prefs.enable_verbose_logging)
        self.report({'INFO'}, "Preferences saved to file")
        return {'FINISHED'}

# -- REGISTER/UNREGISTER --

def register():
    bpy.utils.register_class(DGKPAddonPreferences)
    bpy.utils.register_class(DGKP_OT_SaveSettings)
    
    prefs = bpy.context.preferences.addons.get(__name__)
    if prefs:
        addon_prefs = prefs.preferences
        data = load_preferences_from_file()
        addon_prefs.materials_path = data.get("materials_path", "")
        addon_prefs.enable_verbose_logging = data.get("enable_verbose_logging", False)

    bpy.utils.register_class(DGKP_IMPORTER_OT_IMPORT)
    bpy.utils.register_class(DGKP_IMPORTER_OT_DROP)
    bpy.utils.register_class(DGKP_FH_IMPORT)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

    bpy.utils.register_class(DGKP_IMPORTER_OT_EXPORT)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

def unregister():
    bpy.utils.unregister_class(DGKPAddonPreferences)
    bpy.utils.unregister_class(DGKP_OT_SaveSettings)

    bpy.utils.unregister_class(DGKP_IMPORTER_OT_IMPORT)
    bpy.utils.unregister_class(DGKP_IMPORTER_OT_DROP)
    bpy.utils.unregister_class(DGKP_FH_IMPORT)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

    bpy.utils.unregister_class(DGKP_IMPORTER_OT_EXPORT)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
