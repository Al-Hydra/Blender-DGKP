from .PyBinaryReader.binary_reader import *
import numpy as np

class DGKP(BrStruct):
    def __init__(self) -> None:
        self.textures = []
        self.models = []
        self.animations = []
        self.materials = {}
        self.allFiles = {}
    def __br_read__(self, br: BinaryReader, *args):
        
        self.magic = br.read_str(4)
        br.seek(8,1)
        self.fileCount = br.read_uint32()
        headerSize = br.read_uint32()
        br.seek(28,1)

        self.textures = []
        self.models = []
        self.animations = []
        self.lists = []
        self.materials = {}
        self.allFiles = {}

        for i in range(self.fileCount):
            fileType = br.read_str(4)
            fileHeaderSize = br.read_uint32()
            dataSize = br.read_uint32()
            fileOffset = br.read_uint32()
            fileName = br.read_str(128)

            currentPos = br.pos()
            br.seek(fileOffset)
            fileData = br.read_bytes(dataSize)
            br.seek(currentPos)

            if fileType == "TEXD":
                texBuffer = BinaryReader(fileData, Endian.LITTLE, "cp932")
                file = texBuffer.read_struct(TEXD, None, dataSize)
                self.textures.append(file)
            elif fileType == "MDLD":
                modelBuffer = BinaryReader(fileData, Endian.LITTLE, "cp932")
                file = modelBuffer.read_struct(MDLD)
                file.name = fileName
                self.models.append(file)
            elif fileType == "LIST":
                listBuffer = BinaryReader(fileData, Endian.LITTLE, "cp932")
                file = listBuffer.read_struct(RBLF)
                self.lists.append(file)
            elif fileType == "ANUM":
                anmBuffer = BinaryReader(fileData, Endian.LITTLE, "cp932")
                file = anmBuffer.read_struct(ANUM)
                self.animations.append(file)
            elif fileType == "MATD":
                matBuffer = BinaryReader(fileData, Endian.LITTLE, "cp932")
                file = matBuffer.read_struct(MATF)
                self.materials[file.name] =  file

            else:
                file = DGKPFile(fileName, fileType)
            
            file.data = fileData
            self.allFiles[fileName] = file
    
    
    def __br_write__(self, br: BinaryReader):
        #header
        br.write_str_fixed("DGKP", 4) #magic
        br.write_bytes(b"\x00\x00\x02\x00\x00\x00\x00\x00")
        br.write_uint32(len(self.allFiles))
        br.write_uint32(48)
        br.write_int8([0]*28) #padding


        file_buf_ofs = {}

        #files
        for name, file in self.allFiles.items():
            if file.type == "MDLD":
                br.write_str_fixed(file.type, 4)
                br.write_uint32(144) #header size

                file_buf = BinaryReader()
                file_buf.write_struct(file)
                br.write_uint32(file_buf.size()) #file size

                fileOfsPos = br.pos()
                br.write_uint32(0) #offset
                br.write_str_fixed(name, 128)

                file_bytes = bytes(file_buf.buffer())
            
            elif file.type == "TEXD":
                br.write_str_fixed(file.type, 4)
                br.write_uint32(144) #header size
                
                file_buf = BinaryReader()
                file_buf.write_struct(file)
                br.write_uint32(file_buf.size()) #file size

                fileOfsPos = br.pos()
                br.write_uint32(0) #offset
                br.write_str_fixed(name, 128)

                file_bytes = bytes(file_buf.buffer())

            else:
                br.write_str_fixed(file.type, 4)
                br.write_uint32(144) #header size
                br.write_uint32(len(file.data)) #file size

                fileOfsPos = br.pos()
                br.write_uint32(0) #offset
                br.write_str_fixed(name, 128)

                file_bytes = bytes(file.data)
            
            file_buf_ofs[fileOfsPos] = file_bytes
        
        for ofs, fileBuffer in file_buf_ofs.items():
            currentPos = br.pos()

            br.seek(ofs)
            br.write_uint32(currentPos)

            br.seek(currentPos)
            br.write_bytes(fileBuffer)
            br.align(16)
        


class DGKPFile:
    def __init__(self, name, type) -> None:
        self.type = type
        self.name = name
        self.data = b""
        

class TEXD(BrStruct):
    def __init__(self):
        self.name = ""
        self.type = "TEXD"
        self.data = b""
    def __br_read__(self, br: BinaryReader, fileSize):
        self.magic = br.read_uint16()
        self.width = br.read_uint16()
        self.height = br.read_uint16()
        self.unk = br.read_uint16()
        headerSize = br.read_uint32()
        self.name = br.read_str(64)
        br.seek(4,1)
        
        self.textureData = br.read_bytes(fileSize - headerSize)
    
    def __br_write__(self, br: BinaryReader, *args) -> None:
        br.write_uint16(0)
        br.write_uint16(self.width)
        br.write_uint16(self.height)
        br.write_uint16(self.unk)
        br.write_uint32(80)
        br.write_str_fixed(self.name, 64)
        br.align(16)
        br.write_bytes(self.textureData)

class MDLD(BrStruct):
    def __init__(self):
        self.name = ""
        self.type = "MDLD"
        self.data = b""
    def __br_read__(self, br: BinaryReader):
        self.magic = br.read_str(4)
        self.version = br.read_uint32()
        
        materialsOffset = br.read_uint32()
        self.materialsCount = br.read_uint32()
        bonesOffset = br.read_uint32()
        self.bonesCount = br.read_uint32()
        vertexBufferOffset = br.read_uint32()
        vertexBufferSize = br.read_uint32()
        self.vertexCount = br.read_uint32()
        self.vertexFlags = br.read_uint16()
        self.vertexType = br.read_uint16()
        self.skeletonName = br.read_str(64)
        self.shaderString = br.read_str(128)
        self.boundingBoxData = br.read_bytes(64)

        br.seek(materialsOffset)
        self.materialMeshes = br.read_struct(MDLD_MaterialMesh, self.materialsCount)

        br.seek(bonesOffset)
        self.bones = br.read_struct(MDLD_Bone, self.bonesCount)
        
        br.seek(vertexBufferOffset)
        vertex_buffer = br.read_bytes(vertexBufferSize)
        
        # Using numpy to handle the vertex data more efficiently
        vertex_dtype = [('position', '<f4', 3),
                        ('color', '<u1', 4),
                        ('normal', '<f2', 4),
                        ('uv', '<f2', 2)]
        
        if self.vertexFlags & 32:  # Check if tangent data is present
            vertex_dtype.append(('tangent', '<f2', 4))
        if self.vertexType & 2:  # Check if bone data is present
            vertex_dtype.append(('boneIDs', '<u2', 4))
            vertex_dtype.append(('weights', '<f4', 4))

        self.vertices = np.frombuffer(vertex_buffer, dtype=vertex_dtype)
        
    
    
    def __br_write__(self, br: BinaryReader):
        #header
        br.write_str_fixed("LDMF", 4) #magic
        br.write_uint32(160) #version
        br.write_uint32(296) #mat meshes offset
        br.write_uint32(len(self.materialMeshes)) #mat meshes count

        boneOfPos = br.pos()
        br.write_uint32(0) #bones offset
        br.write_uint32(len(self.bones))# bones count

        vBufOfPos = br.pos()
        br.write_uint32(0) #vertex buffer offset

        vertexSize = 52
        if self.vertexFlags & 32:
            vertexSize = 60

        br.write_uint32(len(self.vertices["positions"]) * vertexSize) #vertex buffer size
        br.write_uint32(len(self.vertices["positions"])) #vertices count
        br.write_uint16(self.vertexFlags)
        br.write_uint16(2)
        br.write_str_fixed(self.skeletonName, 64)
        br.write_str_fixed(self.shaderString, 128)
        br.write_bytes(self.boundingBoxData)

        triangles = []
        
        for mesh in self.materialMeshes:
            mesh: MDLD_MaterialMesh
            br.write_struct(mesh)
        
        for mesh in self.materialMeshes:
            currentPos = br.pos()
            br.seek(mesh.trianglesOffsetPos)
            br.write_uint32(currentPos)

            br.seek(currentPos)

            br.write_bytes(mesh.triangles.tobytes())


        currentPos = br.pos()
        br.seek(boneOfPos)

        br.write_uint32(currentPos)
        br.seek(currentPos)

        for bone in self.bones:
            br.write_struct(bone)
        
        currentPos = br.pos()
        br.seek(vBufOfPos)

        br.write_uint32(currentPos)
        br.seek(currentPos)

        '''for vertex in self.vertices:
            br.write_struct(vertex)'''
            
        # Write vertices using numpy structured array
        dtype = np.dtype([
        ('position', 'f4', 3),
        ('color',    'u1', 4),
        ('normal',   'f2', 4),
        ('uv',       'f2', 2),
        ('tangent',  'f2', 4),
        ('boneIDs',  'u2', 4),
        ('weights',  'f4', 4)
        ], align=False)

        vertex_buffer = np.zeros(len(self.vertices["positions"]), dtype=dtype)

        vertex_buffer["position"] = self.vertices["positions"]
        vertex_buffer["color"] = self.vertices["colors"]
        vertex_buffer["normal"][:, :3] = self.vertices["normals"]
        vertex_buffer["tangent"][:, :3] = self.vertices["tangents"]
        vertex_buffer["uv"] = self.vertices["uvs"]
        vertex_buffer["boneIDs"] = self.vertices["bone_ids"]
        vertex_buffer["weights"] = self.vertices["weights"]

        br.write_bytes(vertex_buffer.tobytes())


class MDLD_MaterialMesh(BrStruct):
    def __init__(self):
        self.name = ""
        self.triangleIndicesCount = 0
        self.triangles = []
    
    def __br_read__(self, br: BinaryReader):
        self.name = br.read_str(64)
        trianglesOffset = br.read_uint32()
        trianglesbufferSize = br.read_uint32()
        self.triangleIndicesCount = br.read_uint32()
        self.type = br.read_uint32()
        self.boundingBoxData = br.read_bytes(96)

        pos = br.pos()

        br.seek(trianglesOffset)
        tribuffer = br.read_bytes(trianglesbufferSize)
        if self.type == 2:
            self.triangles = np.frombuffer(tribuffer, dtype=np.uint16).reshape(-1, 3)
        elif self.type == 4:
            self.triangles = np.frombuffer(tribuffer, dtype=np.uint32).reshape(-1, 3)

        br.seek(pos)
    
    def __br_write__(self, br: BinaryReader):
        br.write_str_fixed(self.name, 64)
        self.trianglesOffsetPos = br.pos()
        br.write_int32(0) #offset will be rewritten later
        br.write_uint32((len(self.triangles) * 3) * 4) #triangles buffer size
        br.write_uint32((len(self.triangles) * 3))  #Indices count
        br.write_uint32(4) # triangle type
        br.write_bytes(self.boundingBoxData)



class MDLD_Bone(BrStruct):
    def __init__(self) -> None:
        self.name = ""
        self.rotation = [0,0,0,0]
        self.position = [0,0,0]
        self.scale = [0,0,0]
        self.parent = 0
    
    def __br_read__(self, br: BinaryReader):
        self.name = br.read_str(32)
        self.rotation = br.read_float32(4)
        self.position = br.read_float32(3)
        self.scale = br.read_float32(3)
        self.parent = br.read_int32()
    
    def __br_write__(self, br: BinaryReader):
        br.write_str_fixed(self.name, 32)
        br.write_float32(self.rotation)
        br.write_float32(self.position)
        br.write_float32(self.scale)
        br.write_int32(self.parent)
    

class MDLD_Vertex(BrStruct):
    def __init__(self) -> None:
        self.position = [0,0,0]
        self.color = [0,0,0,0]
        self.normal = [0,0,0]
        self.tangent = [0,0,0]
        self.uv = [0,0]
        self.boneIDs = [0,0,0,0]  
        self.weights = [0,0,0,0]  
        
    def __br_read__(self, br: BinaryReader, vertexFlags, vertexType):
        self.position = br.read_float32(3)
        self.color = br.read_uint8(4)
        self.normal = br.read_float16(3)
        br.align_pos(4)
        self.uv = br.read_float16(2)

        if vertexFlags & 32:
            self.tangent = br.read_float16(3)
            br.align_pos(4)

        if vertexType & 2:
            self.boneIDs = br.read_uint16(4)
            self.weights = br.read_float32(4)
    
    def __br_write__(self, br: BinaryReader):
        br.write_float32(self.position)
        br.write_uint8(self.color)
        br.write_float16(self.normal)
        br.write_int16(0)
        br.write_float16(self.uv)
        br.write_float16(self.tangent)
        br.write_int16(0)
        br.write_uint16(self.boneIDs)
        br.write_float32(self.weights)

class ANUM(BrStruct):
    def __init__(self) -> None:
        self.name = ""
        self.type = "ANUM"
        self.data = b""
        self.skeletalAnimation = None
        self.cameraAnimation = None
        self.type = "ANUM"
    def __br_read__(self, br: BinaryReader):
        magic = br.read_str(4)

        if magic == "TOMF":
            self.skeletalAnimation = br.read_struct(TOMF)
        elif magic == "CAMF":
            self.cameraAnimation = br.read_struct(CAMF)


class TOMF(BrStruct):
    def __init__(self) -> None:
        self.frameCount = 0
        self.frameRate = 60
        self.bonesCount = 0
        self.modelsCount = 0
        self.curves = []
    def __br_read__(self, br: BinaryReader):
        self.version = br.read_uint32()
        self.name = br.read_str(32)
        br.seek(4,1)
        self.frameCount = br.read_uint32()
        self.frameRate = br.read_uint32()
        self.bonesCount = br.read_uint32()
        self.modelsCount = br.read_uint32()


        self.curves = [br.read_struct(TOMF_Curve, None, i) for i in range(self.bonesCount)]


class TOMF_Curve(BrStruct):
    def __init__(self) -> None:
        self.locationFrames = {}
        self.rotationFrames = {}
        self.scaleFrames = {}
    def __br_read__(self, br: BinaryReader, index = 0):
        self.index = index

        rotationOffset = br.read_uint32()
        rotationCount  = br.read_uint32()
        locationOffset = br.read_uint32()
        locationCount  = br.read_uint32()
        scaleOffset    = br.read_uint32()
        scaleCount     = br.read_uint32()

        pos = br.pos()

        # --- 1. ROTATION: (int32, float32[4]) ---
        if rotationCount > 0:
            br.seek(rotationOffset)
            rotation_data = br.read_bytes(rotationCount * (4 + 16))
            self.rotationFrames = np.frombuffer(rotation_data, dtype=[('frame', '<i4'), ('quat', '<f4', 4)])

        # --- 2. LOCATION: (int32, float32[3]) ---
        if locationCount > 0:
            br.seek(locationOffset)
            location_data = br.read_bytes(locationCount * (4 + 12))
            self.locationFrames = np.frombuffer(location_data, dtype=[('frame', '<i4'), ('pos', '<f4', 3)])

        # --- 3. SCALE: (int32, float32[3]) ---
        if scaleCount > 0:
            br.seek(scaleOffset)
            scale_data = br.read_bytes(scaleCount * (4 + 12))
            self.scaleFrames = np.frombuffer(scale_data, dtype=[('frame', '<i4'), ('scale', '<f4', 3)])

        br.seek(pos)


class MATF(BrStruct):
    def __init__(self) -> None:
        self.name = ""
        self.type = "MATD"
        self.data = b""
    def __br_read__(self, br: BinaryReader):
        self.magic = br.read_str(4)
        self.version = br.read_uint32()
        self.name = br.read_str(64)

        if self.version == 100:
            br.seek(208,1)
        else:
            self.materialFormat = br.read_str(64)
            self.vertexShader = br.read_str(64)
            self.pixelShader = br.read_str(64)
            self.params = br.read_float32(14)

        self.texturesCount = br.read_uint32()

        self.textures = [br.read_str(64) for i in range(self.texturesCount)]


class CAMF(BrStruct):
    def __br_read__(self, br: BinaryReader):
        self.version = br.read_uint32()
        self.headerSize = br.read_uint32()
        self.unk = br.read_uint32()
        self.name = br.read_str(32)
        self.cameraCount = br.read_int32()
        framesOffset = br.read_uint32()
        self.frameCount = br.read_uint16()
        self.frameRate = br.read_uint16()
        self.defaultFoV = br.read_float32()

        self.frames = {}

        pos = br.pos()
        br.seek(framesOffset)
        
        # --- 1. FRAMES: (int32, float32[3], float32[3], float32[3], float32) ---
        '''cam_buffer = br.read_bytes(self.frameCount * (4 + 12 + 12 + 12 + 4))
        self.frames = np.frombuffer(cam_buffer, dtype=[('frame', '<i4'),
                                                       ('location', '<f4', 3),
                                                       ('rotation', '<f4', 3),
                                                       ('scale', '<f4', 3),
                                                       ('fov', '<f4')])'''
        

        for i in range(self.frameCount):
            location = br.read_float32(3)
            rotation = br.read_float32(3)
            scale = br.read_float32(3)
            fov = br.read_float32()

            frame = br.read_int32()

            self.frames[frame] = (location, rotation, scale, fov)

        br.seek(pos)


class RBLF(BrStruct):
    def __init__(self) -> None:
        self.name = "scene"
        self.type = "RBLF"
        self.objects = []
        self.objectGroups = []
    
    def __br_read__(self, br: BinaryReader):
        self.magic = br.read_str(4)
        self.version = br.read_uint32()
        self.unk = br.read_uint32()
        self.unk2 = br.read_uint32()
        self.objCount = br.read_uint32()
        self.objOffset = br.read_uint32()
        self.objGroupsCount = br.read_uint32()
        self.objGroupsOffset = br.read_uint32()
        self.count3 = br.read_uint32()
        self.offset3 = br.read_uint32()
        br.seek(self.objOffset)
        self.objects = br.read_struct(RBLF_Object, self.objCount)
        
        br.seek(self.objGroupsOffset)
        self.objectGroups = br.read_struct(RBLF_ObjectGroup, self.objGroupsCount)

class RBLF_Object(BrStruct):
    def __init__(self) -> None:
        self.name = ""
        self.location = [0, 0, 0]
        self.rotation = [0, 0, 0, 0]
        self.scale = [0, 0, 0]
        self.unk = 0
        self.flags = 0
    
    def __br_read__(self, br: BinaryReader):
        self.name = br.read_str(64)
        self.location = br.read_float32(3)
        self.rotation = br.read_float32(4)
        self.scale = br.read_float32(3)
        self.unk = br.read_int32()
        self.flags = br.read_uint32()
    
    def __br_write__(self, br: BinaryReader):
        br.write_str_fixed(self.name, 64)
        br.write_float32(self.location)
        br.write_float32(self.rotation)
        br.write_float32(self.scale)
        br.write_int32(self.unk)
        br.write_uint32(self.flags)


class RBLF_ObjectGroup(BrStruct):
    def __init__(self) -> None:
        self.min = [0, 0, 0, 0]
        self.max = [0, 0, 0, 0]
        self.objectCount = 0
        self.objectIndexOffset = 0
        self.unk2 = 0
        self.unk3 = 0
        self.objectIndices = []
    
    def __br_read__(self, br: BinaryReader):
        self.min = br.read_float32(4)
        self.max = br.read_float32(4)
        self.objectCount = br.read_uint32()
        self.objectIndexOffset = br.read_uint32()
        self.unk2 = br.read_uint32()
        self.unk3 = br.read_uint32()

        pos = br.pos()
        br.seek(self.objectIndexOffset)
        self.objectIndices = br.read_uint32(self.objectCount)
        br.seek(pos)
    
    def __br_write__(self, br: BinaryReader):
        br.write_float32(self.min)
        br.write_float32(self.max)
        br.write_uint32(self.objectCount)
        self.objectIndexOffsetPos = br.pos()
        br.write_int32(0) #offset will be rewritten later
        br.write_uint32(self.unk2)
        br.write_uint32(self.unk3)


def read_dgkp(path):
    with open(path, "br") as f:
        filebytes = f.read()

    br = BinaryReader(filebytes, Endian.LITTLE, "cp932")

    dgkp: DGKP = br.read_struct(DGKP)

    return dgkp


def write_dgkp(path,  dgkp: DGKP):
    br = BinaryReader(bytearray(), Endian.LITTLE, encoding= "cp932")
    br.write_struct(dgkp)
    with open(path, "wb") as f:
        f.write(br.buffer())

