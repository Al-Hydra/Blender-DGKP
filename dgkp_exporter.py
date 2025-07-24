import bpy, bmesh
import os, time
from time import perf_counter
from bpy.props import CollectionProperty, StringProperty
from bpy.types import Operator, MeshLoopTriangle
from mathutils import Vector, Quaternion, Matrix, Euler
from bpy_extras.io_utils import ExportHelper
from math import radians, tan
from .lib.dgkp import *
import cProfile
import numpy as np
class DGKP_IMPORTER_OT_EXPORT(Operator, ExportHelper):
    bl_idname = 'export_scene.dgkp'
    bl_label = 'Export DGKP'
    filename_ext = '.pac'

    directory: bpy.props.StringProperty(subtype='DIR_PATH', options={'HIDDEN', 'SKIP_SAVE'})
    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    
    export_original_bone_data: bpy.props.BoolProperty(
        name="Use Original Bone Data",
        default=False,
        description="Export bone data using stored matrix/rotation/scale from custom bone properties")

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "export_original_bone_data")
    
    def execute(self, context):
        start_time = time.time()

        dgkp = read_dgkp(self.filepath)
        blender_model = context.object

        dgkp_model = next((m for m in dgkp.models if m.name == blender_model.name), None)
        if not dgkp_model:
            self.report({'ERROR'}, "Matching DGKP model not found.")
            return {"CANCELLED"}
        
        
        #profile = cProfile.Profile()
        #profile.enable()

        # Coordinate system matrix
        up_matrix = Matrix.Rotation(radians(90), 4, 'X')
        up_inv = up_matrix.inverted()
        up_inv_3x3 = up_inv.to_3x3()

        # Bone processing
        blender_bones = sorted([b.name for b in blender_model.data.bones])
        bone_name_to_index = {name: i for i, name in enumerate(blender_bones)}
        dgkp_model.bones = []

        for bone_name in blender_bones:
            bone = blender_model.data.bones[bone_name]
            bone_matrix = up_inv @ bone.matrix_local
            loc, rot, scale = bone_matrix.decompose()
            if self.export_original_bone_data and "orig_matrix" in bone:
                loc, rot, scale = Matrix(bone["orig_matrix"]).decompose()
            else:
                bone_matrix = up_inv @ bone.matrix_local
                loc, rot, scale = bone_matrix.decompose()

            b = MDLD_Bone()
            b.name = bone.name
            b.position = list(loc)
            b.rotation = [rot.x, rot.y, rot.z, rot.w]
            b.scale = list(scale)
            b.parent = bone_name_to_index.get(bone.parent.name, -1) if bone.parent else -1
            dgkp_model.bones.append(b)

        # Mesh
        mesh_obj = blender_model.children[0]
        blender_mesh = mesh_obj.data
        blender_mesh.calc_loop_triangles()
        blender_mesh.calc_tangents()        
        
        def extract_loop_data_numpy(mesh_obj, bone_name_to_index, up_matrix, max_influences=4):
            mesh = mesh_obj.data
            mesh.calc_loop_triangles()

            num_loops = len(mesh.loops)
            num_verts = len(mesh.vertices)
            num_tris = len(mesh.loop_triangles)

            # === Allocate NumPy arrays ===
            vertex_indices = np.empty(num_loops, dtype=np.int32)
            loop_normals = np.empty((num_loops, 3), dtype=np.float32)
            positions = np.empty((num_loops, 3), dtype=np.float32)
            tangents = np.empty((num_loops, 3), dtype=np.float32)
            uvs = np.zeros((num_loops, 2), dtype=np.float32)
            colors = np.zeros((num_loops, 4), dtype=np.float32)

            mesh.loops.foreach_get("vertex_index", vertex_indices)
            mesh.loops.foreach_get("normal", loop_normals.ravel())

            if mesh.uv_layers:
                mesh.uv_layers.active.data.foreach_get("uv", uvs.ravel())
                uvs[:, 1] = 1 - uvs[:, 1]  # Flip Y

            if mesh.color_attributes:
                mesh.color_attributes[0].data.foreach_get("color_srgb", colors.ravel())
                colors = (colors[:, :4] * 255).astype(np.uint8)

            # === Transform normals ===
            loop_normals = loop_normals[:, [0, 2, 1]] * [1, 1, -1]

            # === Vertex positions (transformed) ===
            vert_positions = np.empty((num_verts, 3), dtype=np.float32)
            mesh.vertices.foreach_get("co", vert_positions.ravel())
            vert_positions = vert_positions[:, [0, 2, 1]] * [1, 1, -1]
            positions[:] = vert_positions[vertex_indices]
            
            # we need a copy of the mesh without the custom normals for outlines
            mesh2 = mesh.copy()
            # reset normals
            if mesh2.attributes.get("custom_normal"):
                mesh2.attributes.remove(mesh2.attributes["custom_normal"])

            # === normals as tangents ===
            vert_normals = np.empty((num_verts, 3), dtype=np.float32)
            mesh2.vertices.foreach_get("normal", vert_normals.ravel())
            # swizzle to match the target format
            vert_normals = vert_normals[:, [0, 2, 1]] * [1, 1, -1]  # Assuming original normals are in (X, Z, Y) order
            tangents[:] = vert_normals[vertex_indices]

            # remove mesh2
            bpy.data.meshes.remove(mesh2)

            # === Fast Bone Weights ===
            vertex_groups = mesh_obj.vertex_groups
            bone_ids = np.zeros((num_loops, max_influences), dtype=np.uint16)
            weights = np.zeros((num_loops, max_influences), dtype=np.float32)

            # Flatten weight data
            weight_data = []
            for v in mesh.vertices:
                for g in v.groups:
                    name = vertex_groups[g.group].name
                    if name in bone_name_to_index:
                        weight_data.append((v.index, bone_name_to_index[name], g.weight))

            if weight_data:
                weight_data = np.array(weight_data, dtype=np.float32)
                vi = weight_data[:, 0].astype(np.int32)
                bi = weight_data[:, 1].astype(np.int32)
                w  = weight_data[:, 2]

                structured = np.zeros(len(weight_data), dtype=[('v', np.int32), ('b', np.int32), ('w', np.float32)])
                structured['v'] = vi
                structured['b'] = bi
                structured['w'] = w

                sorted_data = np.sort(structured, order=['v', 'w'])[::-1]

                v_bone_ids = np.zeros((num_verts, max_influences), dtype=np.uint16)
                v_weights = np.zeros((num_verts, max_influences), dtype=np.float32)
                counts = np.zeros((num_verts,), dtype=np.int32)

                for entry in sorted_data:
                    v = entry['v']
                    i = counts[v]
                    if i < max_influences:
                        v_bone_ids[v, i] = entry['b']
                        v_weights[v, i] = entry['w']
                        counts[v] += 1

                # Normalize
                total = v_weights.sum(axis=1, keepdims=True)
                v_weights /= total + 1e-8

                # Broadcast to loops
                bone_ids[:] = v_bone_ids[vertex_indices]
                weights[:] = v_weights[vertex_indices]
            else:
                # No weights? fallback to (0, 0, 0, 1)
                weights[:, 3] = 1.0

            # === Triangle index data ===
            loop_tri_indices = np.empty((num_tris, 3), dtype=np.uint32)
            material_indices = np.empty(num_tris, dtype=np.uint8)
            mesh.loop_triangles.foreach_get("loops", loop_tri_indices.ravel())
            mesh.loop_triangles.foreach_get("material_index", material_indices)

            return {
                "positions": positions,
                "normals": loop_normals,
                "tangents": tangents,
                "uvs": uvs,
                "colors": colors,
                "bone_ids": bone_ids,
                "weights": weights,
                "loop_tri_indices": loop_tri_indices,
                "material_indices": material_indices,
                "vertex_indices": vertex_indices
            }
            
        loop_data = extract_loop_data_numpy(mesh_obj, bone_name_to_index, up_matrix)
        
        # Sort the material indices once
        sorted_idx = np.argsort(loop_data['material_indices'])
        sorted_materials = loop_data['material_indices'][sorted_idx]
        sorted_triangles = loop_data['loop_tri_indices'][sorted_idx]

        # Find boundaries where material changes
        mat_change = np.where(np.diff(sorted_materials) != 0)[0] + 1

        # Split triangles using those boundaries
        triangle_groups = np.split(sorted_triangles, mat_change)
        
        # remove material indeces, vertex indices and loop tri indices
        for key in ['material_indices', 'vertex_indices', 'loop_tri_indices']:
            loop_data.pop(key, None)
        
        dgkp_model.vertices = loop_data
        
        for i, mesh in enumerate(dgkp_model.materialMeshes):
            mesh.triangles = triangle_groups[i] if i < len(triangle_groups) else np.array([], dtype=np.uint32)
        
        write_dgkp(f"{self.filepath}", dgkp)


        #profile.disable()
        #profile.print_stats(sort='time')
        elapsed = time.time() - start_time
        msg = f"Exported {len(loop_data['positions'])} unique vertices in {elapsed:.2f}s"
        print(msg)
        self.report({'INFO'}, msg)

        return {'FINISHED'}
        


def menu_func_export(self, context):
    self.layout.operator(DGKP_IMPORTER_OT_EXPORT.bl_idname,
                        text='DGKP Archive Exporter')