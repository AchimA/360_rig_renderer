import bpy
import os
from bpy.types import Operator
from bpy.props import StringProperty


class COLMAP_RIG_OT_render(Operator):
    bl_idname = 'colmap_rig.render'
    bl_label = 'Render all rigs to folders'
    bl_description = 'Render frames for every visible camera in each collection into the COLMAP folder layout'

    # popup directory selector (defaults to blend file folder when possible)
    filepath = StringProperty(
        name="Output Path",
        description="Folder to write rendered images",
        default="",
        subtype='DIR_PATH',
    )

    def invoke(self, context, event):
        # set default to the blend file folder when available
        if not self.filepath:
            blend_path = bpy.data.filepath
            if blend_path:
                import os as _os
                self.filepath = _os.path.dirname(blend_path)
        # open the file browser for directory selection
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}



    def execute(self, context):
        scene = context.scene
        out_base = bpy.path.abspath(self.filepath or getattr(scene, 'colmap_rig_output_path', '') or "")
        img_format = scene.colmap_rig_image_format
        pad = scene.colmap_rig_zero_pad


        start = scene.frame_start
        end = scene.frame_end


        depsgraph = context.evaluated_depsgraph_get()


        # gather rigs and visible cameras
        rigs = []
        for coll in bpy.data.collections:
            cams = [obj for obj in coll.objects if obj.type == 'CAMERA' and not obj.hide_render and not obj.hide_viewport]
            if not cams:
                continue
            rigs.append((coll.name, cams))


        if not rigs:
            self.report({'WARNING'}, 'No rigs (collections with visible cameras) found')
            return {'CANCELLED'}


        original_camera = scene.camera
        orig_filepath = scene.render.filepath
        orig_format = scene.render.image_settings.file_format
        orig_engine = scene.render.engine


        # set image format
        scene.render.image_settings.file_format = img_format


        for frame in range(start, end + 1):
            scene.frame_set(frame)


            for rig_name, cams in rigs:
                for cam in cams:
                    # ensure output directory
                    cam_folder = os.path.join(out_base, rig_name, cam.name)
                    os.makedirs(cam_folder, exist_ok=True)


                    filename = f"image{str(frame).zfill(pad)}.jpg" if img_format == 'JPEG' else f"image{str(frame).zfill(pad)}.png"
                    filepath = os.path.join(cam_folder, filename)


                    # set scene camera to this camera and render
                    scene.camera = cam
                    scene.render.filepath = filepath


                    # ensure we're using evaluated object for constraints/parents
                    # Blender's render will use evaluated depsgraph automatically for final transform
                    bpy.ops.render.render(write_still=True)


        # restore
        scene.camera = original_camera
        scene.render.filepath = orig_filepath
        scene.render.image_settings.file_format = orig_format
        scene.render.engine = orig_engine


        self.report({'INFO'}, f'Rendered frames {start}-{end} for {len(rigs)} rigs into {out_base}')
        return {'FINISHED'}

classes = (
    COLMAP_RIG_OT_render,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)