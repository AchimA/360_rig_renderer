

import bpy
import importlib

module_names = (
    'rig_manager',
    'rig_json_maker',
    'renderer',
    'ui',
    )


##############################################################################
# Add-On Handling
##############################################################################
def register_properties():
    from bpy.props import StringProperty, EnumProperty, IntProperty

    # register properties only if they don't already exist

    if not hasattr(bpy.types.Scene, 'colmap_rig_image_format'):
        bpy.types.Scene.colmap_rig_image_format = EnumProperty(
        name='Image Format',
        description='Image file format for rendered frames',
        items=(
            ('JPEG', 'JPEG', 'JPEG format'),
            ('PNG', 'PNG', 'PNG format'),
        ),
        default='JPEG',
    )


def unregister_properties():
    for name in (
        'colmap_rig_image_format',
    ):
        if hasattr(bpy.types.Scene, name):
            delattr(bpy.types.Scene, name)

# This list will be filled with the actual module objects at registration
__modules = []

def register():
    # Clear the list on a re-register (e.g., F8)
    __modules.clear()
    # register scene properties first
    register_properties()
    
    for name in module_names:
        try:
            # Dynamically import the module.
            # The f'.{name}' and __package__ are crucial for relative imports
            module = importlib.import_module(f'.{name}', __package__)
            module.register()
            __modules.append(module)
            print(f'Registered module: {name}')
        except ImportError:
            print(f'Error: Could not import module {name}')
        except Exception as e:
            print(f'Error registering module {name}: {e}')
    
def unregister():
    # Unregister in the reverse order to avoid dependency issues
    for module in reversed(__modules):
        try:
            module.unregister()
            print(f'Unregistered module: {module.__name__}')
        except Exception as e:
            print(f'Error unregistering module {module.__name__}: {e}')
            
    # Clear the list
    __modules.clear()
    # remove scene properties
    unregister_properties()

if __name__ == '__main__':
    register()