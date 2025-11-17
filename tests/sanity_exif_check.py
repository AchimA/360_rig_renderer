import bpy
import sys
import os

# Ensure add-on modules are importable
EXT_DIR = os.path.dirname(os.path.dirname(__file__))
if EXT_DIR not in sys.path:
    sys.path.insert(0, EXT_DIR)

# Import and register only needed modules
import rig_manager as rm
import renderer as rndr

try:
    rm.register()
    rndr.register()
except Exception as e:
    print(f"[TEST] Register failed: {e}")

scene = bpy.context.scene

# Output path
out_base = os.path.join(EXT_DIR, "_test_output")
os.makedirs(out_base, exist_ok=True)
scene.render.filepath = out_base
scene.render.image_settings.file_format = 'JPEG'

# Clear default cameras in master collection to avoid confusion
for obj in list(bpy.data.objects):
    if obj.type == 'CAMERA' and obj.users_scene:
        for sc in obj.users_scene:
            try:
                sc.collection.objects.unlink(obj)
            except Exception:
                pass

# Helper: make a camera
def make_cam(name, coll, loc=(0,0,0), rot=(0,0,0), lens=35.0, sensor=36.0):
    camd = bpy.data.cameras.new(name)
    camo = bpy.data.objects.new(name, camd)
    camo.location = loc
    camo.rotation_euler = rot
    camd.lens = lens
    camd.sensor_width = sensor
    coll.objects.link(camo)
    return camo

# Create Equirect rig with two cameras
item1 = scene.rig_collection.add()
item1.name = 'EquirectRig'
item1.rig_type = 'EQUIRECT_360'
item1.include_in_json = True
item1.do_render = True
item1.start_frame = 1
item1.end_frame = 1
item1.frame_step = 1
item1.render_resolution = (640, 360)

coll1 = rm.create_rig_collection(item1)
make_cam('Cam_A', coll1, loc=(0,0,0))
make_cam('Cam_B', coll1, loc=(0,0,0))

# Create Perspective rig with one camera
item2 = scene.rig_collection.add()
item2.name = 'PerspectiveRig'
item2.rig_type = 'PERSPECTIVE'
item2.include_in_json = True
item2.do_render = True
item2.start_frame = 1
item2.end_frame = 1
item2.frame_step = 1
item2.render_resolution = (640, 360)

coll2 = rm.create_rig_collection(item2)
make_cam('Cam_P', coll2, loc=(0,0,0))

# Run render operator
res = bpy.ops.colmap_rig.render()
print(f"[TEST] Render operator result: {res}")

# Validate EXIF
try:
    import piexif
    print("[TEST] piexif available; validating EXIF...")

    def has_exif(jpg_path):
        try:
            ex = piexif.load(jpg_path)
            # If either 0th or Exif dicts have content, treat as EXIF present
            return bool(ex.get('0th')) or bool(ex.get('Exif'))
        except Exception:
            return False

    eq_dir = os.path.join(out_base, 'EquirectRig')
    pe_dir = os.path.join(out_base, 'PerspectiveRig')

    eq_files = []
    pe_files = []
    for root, _, files in os.walk(eq_dir):
        eq_files += [os.path.join(root, f) for f in files if f.lower().endswith('.jpg')]
    for root, _, files in os.walk(pe_dir):
        pe_files += [os.path.join(root, f) for f in files if f.lower().endswith('.jpg')]

    eq_ok = all(has_exif(p) for p in eq_files) and len(eq_files) > 0
    pe_ok = all(not has_exif(p) for p in pe_files) and len(pe_files) > 0

    print(f"[RESULT] Equirect EXIF present: {eq_ok} ({len(eq_files)} files)")
    print(f"[RESULT] Perspective EXIF absent: {pe_ok} ({len(pe_files)} files)")

except ImportError:
    print("[TEST] piexif not installed; skipping EXIF validation but render completed.")

print('[TEST] Done')
