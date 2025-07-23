import bpy, bmesh
import os
from time import time, perf_counter
from bpy.props import CollectionProperty, StringProperty
from mathutils import Vector, Quaternion, Matrix, Euler
from bpy_extras.io_utils import ImportHelper
from math import radians, tan
from .lib.dgkp import *
import cProfile
import pstats

class DGKP_IMPORTER_OT_IMPORT(bpy.types.Operator, ImportHelper):
    bl_label = "Import DGKP"
    bl_idname = "import_scene.dgkp"


    files: CollectionProperty(type=bpy.types.OperatorFileListElement, options={'HIDDEN', 'SKIP_SAVE'}) # type: ignore
    directory: StringProperty(subtype='DIR_PATH', options={'HIDDEN', 'SKIP_SAVE'}) # type: ignore
    filepath: StringProperty(subtype='FILE_PATH') # type: ignore


    def execute(self, context):

        start_time = perf_counter()
        addon_prefs = bpy.context.preferences.addons[__package__].preferences
        materials_path = addon_prefs.materials_path

        for file in self.files:
            
            self.filepath = os.path.join(self.directory, file.name)
            import_dgkp(self.filepath, materials_path)
        
        elapsed_s = "{:.2f}s".format(perf_counter() - start_time)
        self.report({'INFO'}, "DGKP archives imported in " + elapsed_s)

        return {'FINISHED'}
    

class DGKP_IMPORTER_OT_DROP(bpy.types.Operator):
    bl_label = "Import DGKP"
    bl_idname = "import_scene.drop_dgkp"


    files: CollectionProperty(type=bpy.types.OperatorFileListElement, options={'HIDDEN', 'SKIP_SAVE'}) # type: ignore
    directory: StringProperty(subtype='DIR_PATH', options={'HIDDEN', 'SKIP_SAVE'}) # type: ignore
    filepath: StringProperty(subtype='FILE_PATH') # type: ignore


    def execute(self, context):

        start_time = perf_counter()
        addon_prefs = bpy.context.preferences.addons[__package__].preferences
        materials_path = addon_prefs.materials_path

        for file in self.files:
            
            self.filepath = os.path.join(self.directory, file.name)
            import_dgkp(self.filepath, materials_path)
        
        elapsed_s = "{:.2f}s".format(perf_counter() - start_time)
        self.report({'INFO'}, "DGKP archives imported in " + elapsed_s)
        
        return {'FINISHED'}


class DGKP_FH_IMPORT(bpy.types.FileHandler):
    bl_idname = "DGKP_FH_import"
    bl_label = "File handler for DGKP archives"
    bl_import_operator = "import_scene.drop_dgkp"
    bl_file_extensions = ".pac;.lev"

    @classmethod
    def poll_drop(cls, context):
        return (context.area and context.area.type == 'VIEW_3D')
    
    def draw():
        pass

def import_dgkp(filePath, materialspath):
        
    dgkp:DGKP = read_dgkp(filePath)
    if materialspath:
        materialsDGKP: DGKP = read_dgkp(materialspath)
    else:
        materialsDGKP = DGKP()

    up_matrix = Matrix.Rotation(radians(90), 4, 'X')

    def add_material(material, material_name):

        # Check if the material already exists
        blender_material = bpy.data.materials.get(material_name)
        if not blender_material:
            blender_material = bpy.data.materials.new(material_name)
            blender_material.use_nodes = True

            # Clear default nodes
            nodes = blender_material.node_tree.nodes
            links = blender_material.node_tree.links
            nodes.clear()

            # Create nodes
            tex_node = nodes.new("ShaderNodeTexImage")
            tex_node.image = bpy.data.images.get(material.textures[0]) if material and material.textures else None
            tex_node.location = (-800, 0)

            rgb_curves = nodes.new("ShaderNodeRGBCurve")
            rgb_curves.location = (-600, 0)

            # Set a similar curve (example curve)
            curve = rgb_curves.mapping.curves[3]  # Use the 'C' channel
            curve.points.new(0.91, 0.57)
            rgb_curves.mapping.update()

            color_attr = nodes.new("ShaderNodeVertexColor")
            color_attr.location = (-1000, -300)

            gamma_attr = nodes.new("ShaderNodeGamma")
            gamma_attr.inputs[1].default_value = 0.455
            gamma_attr.location = (-800, -300)

            separate = nodes.new("ShaderNodeSeparateColor")
            separate.location = (-600, -300)

            attr_muladd = nodes.new("ShaderNodeMath")
            attr_muladd.operation = 'MULTIPLY_ADD'
            attr_muladd.inputs[1].default_value = 2.0
            attr_muladd.inputs[2].default_value = -1.0
            attr_muladd.use_clamp = True
            attr_muladd.location = (-400, -300)

            diffuse = nodes.new("ShaderNodeBsdfDiffuse")
            diffuse.inputs['Roughness'].default_value = 0.0
            diffuse.location = (-1000, 200)

            shader_to_rgb = nodes.new("ShaderNodeShaderToRGB")
            shader_to_rgb.location = (-800, 200)

            gamma = nodes.new("ShaderNodeGamma")
            gamma.inputs[1].default_value = 0.5
            gamma.location = (-600, 200)

            lighting_muladd = nodes.new("ShaderNodeMath")
            lighting_muladd.operation = 'MULTIPLY_ADD'
            lighting_muladd.inputs[1].default_value = 2.0
            lighting_muladd.inputs[2].default_value = -0.5
            lighting_muladd.use_clamp = True
            lighting_muladd.location = (-400, 200)

            combined = nodes.new("ShaderNodeMath")
            combined.operation = 'MULTIPLY'
            combined.use_clamp = True
            combined.location = (-200, 200)

            final_mask = nodes.new("ShaderNodeMath")
            final_mask.operation = 'MULTIPLY_ADD'
            final_mask.inputs[1].default_value = 0.5
            final_mask.inputs[2].default_value = 0.5
            final_mask.use_clamp = True
            final_mask.location = (0, 200)

            greater_than = nodes.new("ShaderNodeMath")
            greater_than.operation = 'GREATER_THAN'
            greater_than.inputs[1].default_value = 0.5
            greater_than.use_clamp = True
            greater_than.location = (200, 200)

            mix_rgb = nodes.new("ShaderNodeMixRGB")
            mix_rgb.blend_type = 'MIX'
            mix_rgb.inputs['Fac'].default_value = 1.0
            mix_rgb.use_clamp = True
            mix_rgb.location = (400, 100)

            multiply_final = nodes.new("ShaderNodeMixRGB")
            multiply_final.blend_type = 'MULTIPLY'
            multiply_final.inputs['Fac'].default_value = 1.0
            multiply_final.location = (600, 100)

            output = nodes.new("ShaderNodeOutputMaterial")
            output.location = (800, 100)

            # Link nodes
            links.new(tex_node.outputs['Color'], rgb_curves.inputs['Color'])
            links.new(color_attr.outputs['Color'], gamma_attr.inputs['Color'])
            links.new(gamma_attr.outputs['Color'], separate.inputs['Color'])
            links.new(separate.outputs['Red'], attr_muladd.inputs[0])

            links.new(diffuse.outputs['BSDF'], shader_to_rgb.inputs['Shader'])
            links.new(shader_to_rgb.outputs['Color'], gamma.inputs['Color'])
            links.new(gamma.outputs['Color'], lighting_muladd.inputs[0])
            links.new(lighting_muladd.outputs[0], combined.inputs[0])
            links.new(attr_muladd.outputs[0], combined.inputs[1])
            links.new(combined.outputs[0], final_mask.inputs[0])
            links.new(final_mask.outputs[0], greater_than.inputs[0])
            links.new(greater_than.outputs[0], mix_rgb.inputs['Fac'])

            links.new(rgb_curves.outputs['Color'], mix_rgb.inputs[1])
            links.new(tex_node.outputs['Color'], mix_rgb.inputs[2])

            links.new(mix_rgb.outputs['Color'], multiply_final.inputs['Color1'])
            links.new(tex_node.outputs['Alpha'], multiply_final.inputs['Color2'])

            links.new(multiply_final.outputs['Color'], output.inputs['Surface'])

        return blender_material


    def add_bones(bone, armature, up_matrix):
        bbone = armature.edit_bones.new(bone.name)
        bbone.use_deform = True
        
        #check the scale sign and adjust the rotation accordingly
        rotation = Quaternion((bone.rotation[3], bone.rotation[0], bone.rotation[1], bone.rotation[2]))

        transform = Matrix.LocRotScale(bone.position, rotation, (1, 1, 1))

        # Apply up_matrix to the transform
        final_matrix = up_matrix @ transform

        # Set head and tail positions directly
        bbone.head = final_matrix.translation

        # Calculate tail position a small distance along the Y axis of the bone
        tail_offset = final_matrix @ Vector((0, 0.1, 0)) - final_matrix.translation
        bbone.tail = bbone.head + tail_offset

        # Use up_matrix-transformed direction to set roll
        bbone.align_roll((final_matrix @ Vector((0, 0, 1)) - bbone.head).normalized())

        # Store debug data
        bbone["orig_matrix"] = transform
        bbone["final_matrix"] = final_matrix
        bbone["rotation"] = rotation

        return bbone


    if dgkp.textures:
        for texture in dgkp.textures:
            texture: TEXD
            
            if not bpy.data.images.get(texture.name):
                img = bpy.data.images.new(texture.name, texture.width, texture.height, alpha=True)
                img.pack(data=bytes(texture.textureData), data_len=len(texture.textureData))
                img.source = 'FILE'


    if dgkp.models:
        
        
        for mdl in dgkp.models:
            mdl: MDLD
            armature = bpy.data.armatures.new(mdl.name)
            armature.display_type = 'STICK'
            armature_obj = bpy.data.objects.new(mdl.name, armature)
            armature_obj.show_in_front = True

            bpy.context.collection.objects.link(armature_obj)

            bpy.context.view_layer.objects.active = armature_obj
            bpy.ops.object.mode_set(mode='EDIT')
            
            bones = [add_bones(bone, armature, up_matrix) for bone in mdl.bones]
            
            

            for i, bone in enumerate(mdl.bones):
                bone: MDLD_Bone
                
                bbone = bones[i]
                if bone.parent > -1:
                    parent_bbone = bones[bone.parent]
                    
                else:
                    parent_bbone = None
                
                bbone.parent = parent_bbone

            bpy.ops.object.mode_set(mode='OBJECT')


            meshdata = bpy.data.meshes.new(mdl.skeletonName)
            mesh_obj = bpy.data.objects.new(mdl.skeletonName, meshdata)

            mesh_obj.parent = armature_obj

            armature_modifier = mesh_obj.modifiers.new(name = mdl.skeletonName, type = 'ARMATURE')
            armature_modifier.object = armature_obj

            for bone in mdl.bones:
                mesh_obj.vertex_groups.new(name = bone.name)

            bm = bmesh.new()
            uv_layer = bm.loops.layers.uv.new(f"UV")
            color_layer = bm.loops.layers.color.new(f"Color")
            vgroup_layer = bm.verts.layers.deform.new("Weights")

            bm_verts = [bm.verts.new((v[0], -v[2], v[1])) for v in mdl.vertices["position"]]
            
            if mdl.vertexType & 2:  # has weights
                boneIDs = mdl.vertices["boneIDs"]
                weights = mdl.vertices["weights"]

                # Precompute masks of non-zero weights
                nonzero_mask = weights > 0

                for i, v in enumerate(bm_verts):
                    # Select only the non-zero boneIDs and weights for this vertex
                    valid_ids = boneIDs[i][nonzero_mask[i]]
                    valid_weights = weights[i][nonzero_mask[i]]
                    for boneID, weight in zip(valid_ids, valid_weights):
                        v[vgroup_layer][boneID] = weight

            bm.verts.ensure_lookup_table()

            colors = mdl.vertices["color"] / 255.0  # Normalize color values to [0, 1]
            mdl.vertices["uv"][:, 1] = 1.0 - mdl.vertices["uv"][:, 1]  # In-place Y flip
            uvs = mdl.vertices["uv"]  # Now uv is the full 2D array
            for i, mat in enumerate(mdl.materialMeshes):
                mat: MDLD_MaterialMesh
                material = materialsDGKP.materials.get(mat.name)

                meshdata.materials.append(add_material(material, mat.name))

                for tris in mat.triangles:
                    face = bm.faces.new((bm.verts[tris[0]], bm.verts[tris[1]], bm.verts[tris[2]]))
                    face.smooth = True
                    face.material_index = i

                    face.loops[0][uv_layer].uv = uvs[tris[0]]
                    face.loops[1][uv_layer].uv = uvs[tris[1]]
                    face.loops[2][uv_layer].uv = uvs[tris[2]]

                    face.loops[0][color_layer] = colors[tris[0]]
                    face.loops[1][color_layer] = colors[tris[1]]
                    face.loops[2][color_layer] = colors[tris[2]]
            
            bm.to_mesh(meshdata)
            bm.free()
            
            normals = mdl.vertices["normal"][:, [0, 2, 1]] * [1, -1, 1]  # Swizzle Y and Z
            meshdata.normals_split_custom_set_from_vertices(normals)

            #set active color
            mesh_obj.data.color_attributes.render_color_index = 0
            mesh_obj.data.color_attributes.active_color_index = 0

            bpy.context.collection.objects.link(mesh_obj)
    
    if dgkp.lists:
        for lst in dgkp.lists:
            lst: RBLF
            
            for instancedObj in lst.objects:
                instancedObj: RBLF_Object
                
                #search for the object in the scene
                obj = bpy.data.objects.get(instancedObj.name + ".mdl")  # Remove .mdl
                if obj:
                    #construct a matrix from the instanced object
                    obj_matrix = Matrix.LocRotScale(
                        Vector((instancedObj.location[0], -instancedObj.location[2], instancedObj.location[1])),
                        Quaternion((instancedObj.rotation[3], instancedObj.rotation[0], instancedObj.rotation[2], instancedObj.rotation[1])),
                        Vector(instancedObj.scale)
                    )

                    #hide the original object and its children
                    obj.hide_set(True)
                    for child in obj.children:
                        child.hide_set(True)
                    
                    # create an instance of the object and its children
                    instance_obj = obj.copy()
                    instance_obj.data = obj.data
                    bpy.context.collection.objects.link(instance_obj)
                    instance_obj.matrix_world = obj_matrix
                    for child in obj.children:
                        child_instance = child.copy()
                        child_instance.data = child.data
                        
                        child_instance.parent = instance_obj
                        bpy.context.collection.objects.link(child_instance)

    def insertFrames(action, group_name, data_path, values, values_count):
        if not values:
            return

        frames = np.fromiter(values.keys(), dtype=np.float32, count=len(values))
        values_np = np.array(list(values.values()), dtype=np.float32)  # shape (N, values_count)

        for i in range(values_count):
            fc = action.fcurves.new(data_path=data_path, index=i, action_group=group_name)
            fc.keyframe_points.add(len(frames))

            # Use NumPy to create flattened (frame, value) pairs
            co = np.empty((len(frames), 2), dtype=np.float32)
            co[:, 0] = frames
            co[:, 1] = values_np[:, i]

            fc.keyframe_points.foreach_set('co', co.flatten())
            fc.update()

    for anim in dgkp.animations:
        anim: ANUM
        
        if anim.skeletalAnimation:
            sklAnim = anim.skeletalAnimation

            action = bpy.data.actions.new(sklAnim.name)

            #set fps to 30
            bpy.context.scene.render.fps = 60

            #adjust the timeline
            bpy.context.scene.frame_start = 0
            bpy.context.scene.frame_end = sklAnim.frameCount

            target_armature = bpy.context.object
            target_armature.animation_data_create()
            target_armature.animation_data.action = action

            bones = sorted([b.name for b in target_armature.pose.bones])

            up_quat = up_matrix.to_quaternion()
            
            def quat_mul(q1, q2):
                w1, x1, y1, z1 = q1.T
                w2, x2, y2, z2 = q2.T
                return np.array([
                    w1*w2 - x1*x2 - y1*y2 - z1*z2,
                    w1*x2 + x1*w2 + y1*z2 - z1*y2,
                    w1*y2 - x1*z2 + y1*w2 + z1*x2,
                    w1*z2 + x1*y2 - y1*x2 + z1*w2,
                ]).T  # Shape: (N, 4)
            
            for curve in sklAnim.curves:
                curve: TOMF_Curve
                group_name = action.groups.new(name = bones[curve.index]).name
                bone_path = f'pose.bones["{group_name}"]'
                
                bbone = target_armature.data.bones.get(bones[curve.index])
                if bbone.parent:
                    matrix = Matrix(bbone.parent["orig_matrix"]).inverted() @ Matrix(bbone["orig_matrix"])
                else:
                    matrix = Matrix(bbone["orig_matrix"])

                loc, rot, scale = matrix.decompose()
                rot = np.array((rot[0], -rot[1], -rot[2], -rot[3]), dtype=np.float32)

                # Location
                if len(curve.locationFrames):
                    f = curve.locationFrames['frame']
                    v = curve.locationFrames['pos'] - loc
                    insertFrames(action, group_name, f'{bone_path}.location', dict(zip(f, v)), 3)

                # Rotation
                if len(curve.rotationFrames):
                    f = curve.rotationFrames['frame']
                    q = curve.rotationFrames['quat'][:, [3, 0, 1, 2]]  # to wxyz
                    r = quat_mul(rot, q)
                    insertFrames(action, group_name, f'{bone_path}.rotation_quaternion', dict(zip(f, r)), 4)

                # Scale
                if len(curve.scaleFrames):
                    f = curve.scaleFrames['frame']
                    v = curve.scaleFrames['scale'] / scale
                    insertFrames(action, group_name, f'{bone_path}.scale', dict(zip(f, v)), 3)
                

        # convert the rotation part of the up_matrix to a quaternion
        up_quat = up_matrix.to_quaternion()
        flip_quat = Quaternion((1.0, 0.0, 0.0), radians(180))
        camera_up_quat = up_quat @ flip_quat

        if anim.cameraAnimation:
            camAnim = anim.cameraAnimation

            bpy.context.scene.render.fps = 60
            bpy.context.scene.frame_start = 0
            bpy.context.scene.frame_end = camAnim.frameCount

            camera_obj = bpy.context.scene.camera
            if not camera_obj:
                camera = bpy.data.cameras.new("Camera")
                camera_obj = bpy.data.objects.new("Camera", camera)
                bpy.context.collection.objects.link(camera_obj)
                bpy.context.scene.camera = camera_obj

            camera_action = bpy.data.actions.new(f"{camAnim.name} ({camera_obj.name})")
            group_name = camera_action.groups.new(name=camera_obj.name).name

            camera_obj.animation_data_create()
            camera_obj.animation_data.action = camera_action
            camera_obj.scale = (10, 10, 10)
            camera_obj.data.lens = camera_obj.data.sensor_width / (2 * tan(radians(camAnim.defaultFoV) / 2))

            locations = {}
            rotations = {}
            fovs = {}

            for frame, values in camAnim.frames.items():
                loc, rot, scale, fov = values

                # Apply up_matrix to location
                loc = Vector(loc)
                loc.rotate(up_quat)

                rot_rad = [radians(r) for r in rot]
                euler_rot = Euler(rot_rad, 'XYZ')
                euler_rot.rotate(camera_up_quat)
                euler_rot[2] = -euler_rot[2]

                locations[frame] = loc
                rotations[frame] = euler_rot
                fov_rad = radians(camAnim.defaultFoV + fov)
                fovs[frame] = [camera_obj.data.sensor_width / (2 * tan(fov_rad / 2))]

            insertFrames(camera_action, group_name, "location", locations, 3)
            insertFrames(camera_action, group_name, "rotation_euler", rotations, 3)
            insertFrames(camera_action, group_name, "data.lens", fovs, 1)


        


def menu_func_import(self, context):
    self.layout.operator(DGKP_IMPORTER_OT_IMPORT.bl_idname,
                        text='DGKP Archive Importer')