#Simplified BSD License
#
#Copyright (c) 2012, Florian Meyer
#tstscr@web.de
#All rights reserved.
#
#Redistribution and use in source and binary forms, with or without
#modification, are permitted provided that the following conditions are met: 
#
#1. Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer. 
#2. Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution. 
#
#THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
#ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
#WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
#ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
#(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
#LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
#ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
#SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#################################################################

bl_info = {
    "name": "Auto Save Render",
    "author": "tstscr",
    "version": (2, 1),
    "blender": (5, 0, 0),
    "location": "Properties > Render > Auto Save Render",
    "description": "Automatically save the image after rendering",
    "category": "Render"
}

import bpy
from bpy.props import BoolProperty, EnumProperty, PointerProperty, StringProperty
from bpy.app.handlers import persistent
from os.path import dirname, exists, join
from bpy.path import basename
from os import mkdir, listdir
from re import findall
from datetime import datetime

TIMER = None

@persistent
def start_timer(scene, *args):
    global TIMER
    TIMER = datetime.now()

@persistent
def auto_save_render(scene, *args):
    global TIMER
    if TIMER is None:
        TIMER = datetime.now()
        
    render_time = datetime.now() - TIMER
    
    # Defer the save operation by 0.1 seconds to avoid Dependency Graph crashes
    bpy.app.timers.register(lambda: execute_save(scene.name, render_time), first_interval=0.1)

def execute_save(scene_name, render_time):
    scene = bpy.data.scenes.get(scene_name)
    if not scene: 
        return None
        
    props = scene.auto_save_props
    
    if not props.save_after_render:
        return None
        
    # Safety checks for paths
    if not props.use_custom_path and not bpy.data.filepath:
        print("Auto Save: Please save your .blend file first, or enable the Custom Folder option.")
        return None
        
    if props.use_custom_path and not props.custom_save_path:
        print("Auto Save: Custom Folder is enabled, but no directory is selected.")
        return None
        
    rndr = scene.render
    original_format = rndr.image_settings.file_format

    format = props.auto_save_format
    rndr.image_settings.file_format = format
    
    if format == 'OPEN_EXR_MULTILAYER': extension = '.exr'
    elif format == 'JPEG': extension = '.jpg'
    elif format == 'PNG': extension = '.png'
    else: extension = '.png'
    
    # Use "untitled" if the blend file hasn't been saved yet
    blendname = basename(bpy.data.filepath).rpartition('.')[0] if bpy.data.filepath else "untitled"
    
    # Determine the target directory
    if props.use_custom_path:
        # Resolve Blender's relative path (//) to an absolute OS path
        filepath = bpy.path.abspath(props.custom_save_path)
    else:
        filepath = join(dirname(bpy.data.filepath), 'auto_saves')
    
    if not exists(filepath):
        try:
            mkdir(filepath)
        except OSError:
            print("Auto Save: Could not create directory. Check path permissions.")
            rndr.image_settings.file_format = original_format
            return None
  
    if props.auto_save_subfolders:
        filepath = join(filepath, blendname)
        if not exists(filepath):
            mkdir(filepath)

    files = [f for f in listdir(filepath) \
             if f.startswith(blendname) \
             and f.lower().endswith(('.png', '.jpg', '.jpeg', '.exr'))]
    
    highest = 0
    if files:
        for f in files:
            suffix = findall(r'\d+', f.split(blendname)[-1])
            if suffix:
                if int(suffix[-1]) > highest:
                    highest = int(suffix[-1])
    
    save_name = join(filepath, f"{blendname}_{str(highest+1).zfill(3)}{extension}")

    try:
        image = bpy.data.images['Render Result']
    except KeyError:
        print('Auto Save: Render Result not found. Image not saved.')
        rndr.image_settings.file_format = original_format
        return None
    
    print('Auto_Save:', save_name)
    image.save_render(save_name, scene=scene)

    if props.save_blend and bpy.data.filepath:
        save_name_blend = join(filepath, f"{blendname}_{str(highest+1).zfill(3)}.blend")
        print('Blend_Save:', save_name_blend)
        bpy.ops.wm.save_as_mainfile(filepath=save_name_blend, copy=True)

    if props.logfile:
        md_textname = 'save log'
        if md_textname not in bpy.data.texts:
            bpy.data.texts.new(md_textname)
            bpy.data.texts[md_textname].filepath = join(filepath, blendname + '_log.md')
            
        save_name_base = basename(save_name)
        link_text = save_name_base.rpartition('.')[0]
        
        time_str = datetime.now().strftime('{%Y-%m-%d %H:%M}')
        text = "\n**" + link_text + "** " + time_str + " \n![](" + save_name_base + ") \nRender time: " + str(render_time) + " \n"
            
        bpy.data.texts[md_textname].write(text)
 
    rndr.image_settings.file_format = original_format
    
    return None

###########################################################################
class AutoSaveProperties(bpy.types.PropertyGroup):
    save_after_render: BoolProperty(
        name='Save after render',
        default=True,
        description='Automatically save rendered images'
    )
    save_blend: BoolProperty(
        name='with .blend',
        default=True,
        description='Also save a copy of the .blend file'
    )   
    use_custom_path: BoolProperty(
        name='Custom Folder',
        default=False,
        description='Choose a specific folder for auto saves instead of the default //auto_save/'
    )
    custom_save_path: StringProperty(
        name='Directory',
        subtype='DIR_PATH',
        default='',
        description='Select the folder where renders will be saved'
    )
    auto_save_format: EnumProperty(
        name='Auto Save File Format',
        description='File Format for the auto saves.',
        items=[
            ('PNG', 'png', 'Save as png'),
            ('JPEG', 'jpg', 'Save as jpg'),
            ('OPEN_EXR_MULTILAYER', 'exr', 'Save as multilayer exr')
        ],
        default='PNG'
    )
    auto_save_subfolders: BoolProperty(
        name='subfolder',
        default=False,
        description='Save into individual subfolders per blend name'
    )
    logfile: BoolProperty(
        name='logfile',
        default=False,
        description='Log saves to text file'
    )

class RENDER_PT_auto_save(bpy.types.Panel):
    bl_label = "Auto Save Render"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'render'

    def draw(self, context):
        layout = self.layout
        props = context.scene.auto_save_props
        
        split = layout.split()
        
        # Left Column
        col = split.column()
        col.prop(props, 'save_after_render', text='Auto Save Image', toggle=False)
        col.prop(props, 'save_blend', text='with .blend', toggle=False) 
        col.separator()
        col.prop(props, 'use_custom_path')
        
        # Hide the directory browser if the custom path isn't checked
        if props.use_custom_path:
            col.prop(props, 'custom_save_path', text='')

        # Right Column
        col = split.column()    
        col.prop(props, 'auto_save_subfolders', text='in subfolder', toggle=False)
        col.prop(props, 'auto_save_format', text='as', expand=False)
        col.prop(props, 'logfile', text='with log file', toggle=False)

classes = (
    AutoSaveProperties,
    RENDER_PT_auto_save,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.auto_save_props = PointerProperty(type=AutoSaveProperties)
    
    bpy.app.handlers.render_pre.append(start_timer)
    bpy.app.handlers.render_post.append(auto_save_render)
    
def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.auto_save_props
    
    if auto_save_render in bpy.app.handlers.render_post:
        bpy.app.handlers.render_post.remove(auto_save_render)
    if start_timer in bpy.app.handlers.render_pre:
        bpy.app.handlers.render_pre.remove(start_timer)

if __name__ == "__main__":
    register()
