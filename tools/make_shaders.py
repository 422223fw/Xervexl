"""Emit the two fixed, tiny SPIR-V 1.0 shaders matching shaders/arena.*.

This is an assembler for these pass-through shaders, not a GLSL compiler.
It avoids a Vulkan SDK installation and is reproducible with Python alone.
Op codes follow the Khronos SPIR-V 1.0 specification.
"""
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]/"shaders"
OPS = dict(Capability=17, MemoryModel=14, EntryPoint=15, ExecutionMode=16,
           Decorate=71, MemberDecorate=72, TypeVoid=19, TypeFunction=33,
           TypeFloat=22, TypeVector=23, TypePointer=32, TypeStruct=30,
           TypeInt=21, Variable=59, Constant=43, ConstantComposite=44,
           Function=54, Label=248, Load=61, VectorTimesScalar=142, FSub=131,
           CompositeExtract=81, CompositeConstruct=80, AccessChain=65,
           Store=62, Return=253, FunctionEnd=56)


def text(s):
    b = s.encode()+b"\0"
    b += b"\0"*((-len(b))%4)
    return list(struct.unpack("<"+"I"*(len(b)//4), b))


def shader(vertex):
    code=[]
    def op(name,*operands):
        code.extend([((len(operands)+1)<<16)|OPS[name],*operands])
    op("Capability",1)  # Shader
    op("MemoryModel",0,1)  # Logical, GLSL450
    if vertex:
        op("EntryPoint",0,30,*text("main"),10,11,12,13)
        op("Decorate",10,30,0);op("Decorate",11,30,1);op("Decorate",13,30,0)
        op("MemberDecorate",14,0,11,0)  # gl_PerVertex.Position
        op("Decorate",14,2)  # Block
    else:
        op("EntryPoint",4,30,*text("main"),10,11)
        op("ExecutionMode",30,7)  # OriginUpperLeft
        op("Decorate",10,30,0);op("Decorate",11,30,0)
    op("TypeVoid",1);op("TypeFunction",2,1);op("TypeFloat",3,32)
    op("TypeVector",4,3,2);op("TypeVector",5,3,4)
    if vertex:
        op("TypePointer",6,1,4);op("TypePointer",7,1,5);op("TypePointer",8,3,5)
        op("TypeStruct",14,5);op("TypePointer",15,3,14)
        op("TypeInt",16,32,1);op("Constant",16,17,0)
        op("Variable",6,10,1);op("Variable",7,11,1);op("Variable",15,12,3);op("Variable",8,13,3)
        for ident,value in ((18,0.),(19,1.),(20,2.)):
            op("Constant",3,ident,struct.unpack("<I",struct.pack("<f",value))[0])
        op("ConstantComposite",4,21,19,19)
        op("Function",1,30,0,2);op("Label",31)
        op("Load",4,32,10);op("VectorTimesScalar",4,33,32,20);op("FSub",4,34,33,21)
        op("CompositeExtract",3,35,34,0);op("CompositeExtract",3,36,34,1)
        op("CompositeConstruct",5,37,35,36,18,19)
        op("AccessChain",8,38,12,17);op("Store",38,37)
        op("Load",5,39,11);op("Store",13,39)
    else:
        op("TypePointer",6,1,5);op("TypePointer",7,3,5)
        op("Variable",6,10,1);op("Variable",7,11,3)
        op("Function",1,30,0,2);op("Label",31);op("Load",5,32,10);op("Store",11,32)
    op("Return");op("FunctionEnd")
    words=[0x07230203,0x00010000,0,40,0]+code
    return struct.pack("<"+"I"*len(words),*words)


for stage,vertex in (("vert",True),("frag",False)):
    path=ROOT/f"arena.{stage}.spv"
    path.write_bytes(shader(vertex))
    print(f"Wrote {path.name}")
