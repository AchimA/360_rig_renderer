import bpy
import os
import json
import mathutils
from bpy.types import Operator
from bpy.props import StringProperty


def _get_evaluated_matrix(obj, depsgraph):
    """Return the evaluated world matrix for an object using the depsgraph."""
    obj_eval = obj.evaluated_get(depsgraph)
    # ensure we return a copy to avoid mutating Blender's internal data
    return obj_eval.matrix_world.copy()


def _matrix_to_colmap_quat_trans(T):
    # Flip Y (Blender +Y up -> COLMAP +Y down)
    flip_y = mathutils.Matrix.Scale(-1, 4, (0, 1, 0))
    T = flip_y @ T
    q = T.to_quaternion()
    t = T.to_translation()
    return [q.w, q.x, q.y, q.z], [t.x, t.y, t.z]


class COLMAP_RIG_OT_export(Operator):
    bl_idname = 'colmap_rig.export'
    bl_label = 'Export rig JSON for COLMAP'
    bl_description = 'Export rigs (collections) as COLMAP rig JSON'

# --- 1. Define properties for the FileBrowser ---
    # The filepath property is what the file browser uses to return the selected path
    filepath: bpy.props.StringProperty(
        name="File Path",
        description="Folder to write rig_config.json",
        subtype='FILE_PATH',
    )

    # This is a dummy property to correctly open the file browser
    # The name is important: 'files', 'file_name', etc.
    # The file browser will automatically use this to set the default file name.
    filename: bpy.props.StringProperty(
        name="File Name",
        description="*.json file name",
        default="export.json", # --- 3. Default file name
        maxlen=1024,
    )

    # --- 3. Filter for .json files
    filter_glob: bpy.props.StringProperty(
        default="*.json", # Always enforce .txt extension
        options={'HIDDEN'},
        maxlen=255,
    )


    def invoke(self, context, event):
         # Set the initial directory for the file browser
        if bpy.data.filepath:
            # If blend file is saved, start in its directory
            self.filepath = os.path.dirname(bpy.data.filepath)
        else:
            # If not saved, start in user's home directory or a common default
            # For cross-platform, os.path.expanduser('~') is a good choice for home dir
            self.filepath = os.path.expanduser('~') # Or a specific default like "C:\\temp" or "/tmp"

        # Set the default filename *before* invoking the file browser
        self.filename = "rig_config.json" # Ensure default is set every time

        # Open the file browser. The 'INVOKE_DEFAULT' means show the dialog.
        # context.window_manager.fileselect_report(self)
        return context.window_manager.invoke_props_dialog(self, width=800)
        # context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        scene = context.scene
        # chosen path from popup takes precedence; fall back to scene property
        # full_filepath = os.path.join(self.filepath, self.filename)
        out_path = bpy.path.abspath(self.filepath)
        rigs = []
        depsgraph = context.evaluated_depsgraph_get()


        for coll in bpy.data.collections:
            # skip collections if it's deactivaed
            # if  not (coll.exclude or coll.hide_viewport or coll.hide_render):
            #     continue

            # collect visible cameras in this collection
            cams = [
                obj
                for obj
                in coll.objects
                if obj.type == 'CAMERA' and not obj.hide_render and not obj.hide_viewport
                ]

            if not cams:
                continue

            # choose reference camera (first visible). User can modify later if needed.
            ref_cam = cams[0]
            M_ref = _get_evaluated_matrix(ref_cam, depsgraph)

            rig_entry = {"cameras": []}

            for cam in cams:
                M_cam = _get_evaluated_matrix(cam, depsgraph)
                T_cam_ref = M_ref.inverted() @ M_cam


                if cam == ref_cam:
                    cam_entry = {
                    "image_prefix": f"{coll.name}/{cam.name}/",
                    "ref_sensor": True
                    }
                else:
                    quat, trans = _matrix_to_colmap_quat_trans(T_cam_ref)
                    cam_entry = {
                    "image_prefix": f"{coll.name}/{cam.name}/",
                    "cam_from_rig_rotation": quat,
                    "cam_from_rig_translation": trans
                    }


                rig_entry["cameras"].append(cam_entry)


            rigs.append(rig_entry)


        # write file next to output folder
        import os
        os.makedirs(out_path, exist_ok=True)
        json_path = os.path.join(out_path, "rig_config.json")
        with open(json_path, 'w') as f:
            json.dump(rigs, f, indent=4)


        self.report({'INFO'}, f"Exported {len(rigs)} rigs to {json_path}")
        return {'FINISHED'}

    


classes = (
    COLMAP_RIG_OT_export,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)