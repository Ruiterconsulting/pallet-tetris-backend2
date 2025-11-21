from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
import uuid
import os
import base64

# Numeric / mesh libs
import numpy as np
import trimesh

# OpenCascade imports
from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.BRepBndLib import brepbndlib_Add
from OCC.Core.GProp import GProp_GProps
from OCC.Core.BRepGProp import brepgprop_VolumeProperties
from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_FACE
from OCC.Core.BRep import BRep_Tool
from OCC.Core.TopLoc import TopLoc_Location

app = FastAPI()


# ============================
# Helpers
# ============================

def round_f(x, n=3):
    return round(float(x), n)


def analyze_step_file(step_path: str, material: str):
    """
    Lees STEP, bereken bbox, volume, gewicht.
    Geeft (shape, result_dict) terug.
    """
    reader = STEPControl_Reader()
    status = reader.ReadFile(step_path)

    if status != 1:
        raise RuntimeError("Failed to read STEP file")

    reader.TransferRoots()
    shape = reader.OneShape()

    # BOUNDING BOX
    bbox = Bnd_Box()
    brepbndlib_Add(shape, bbox)
    xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()

    length = xmax - xmin
    width = ymax - ymin
    height = zmax - zmin

    # VOLUME
    props = GProp_GProps()
    brepgprop_VolumeProperties(shape, props)
    volume_mm3 = props.Mass()  # mm³

    # DENSITY (kg/m³)
    densities = {
        "steel": 7850,
        "aluminum": 2700,
        "stainless": 8000,
        "copper": 8960,
    }
    density = densities.get(material.lower(), 7850)

    volume_m3 = volume_mm3 / 1_000_000_000.0
    weight_kg = volume_m3 * density

    part_length = round_f(length, 3)
    part_width = round_f(width, 3)
    part_height = round_f(height, 3)

    result = {
        "rawBoundingBox": {
            "xmin": xmin,
            "xmax": xmax,
            "ymin": ymin,
            "ymax": ymax,
            "zmin": zmin,
            "zmax": zmax,
        },
        "partDimensions_mm": {
            "length": part_length,
            "width": part_width,
            "height": part_height,
        },
        "partData": {
            "length_mm": part_length,
            "width_mm": part_width,
            "height_mm": part_height,
            "volume_mm3": round_f(volume_mm3, 3),
            "volume_m3": round_f(volume_m3, 9),
            "weight_kg": round_f(weight_kg, 4),
        },
    }

    return shape, result


def shape_to_glb_base64(shape) -> str:
    """
    Converteer een OpenCascade shape naar een GLB (binary glTF) in base64.
    - Mesht met BRepMesh_IncrementalMesh
    - Leest triangulatie per face
    - Bouwt een Trimesh
    - Exporteert naar GLB bytes
    - Encodeert als base64 string
    """

    # Mesh settings: kun je later tunen
    mesh = BRepMesh_IncrementalMesh(shape, 0.5, True, 0.5, True)
    mesh.Perform()

    vertices = []
    faces = []

    exp = TopExp_Explorer(shape, TopAbs_FACE)
    for face in exp:
        loc = TopLoc_Location()
        triangulation = BRep_Tool.Triangulation(face, loc)

        if triangulation is None:
            continue

        trsf = loc.Transformation()
        nodes = triangulation.Nodes()
        triangles = triangulation.Triangles()

        # Offset voor indices
        v_offset = len(vertices)

        # Nodes
        for i in range(1, triangulation.NbNodes() + 1):
            pnt = nodes.Value(i)
            pnt_tr = pnt.Transformed(trsf)
            vertices.append([pnt_tr.X(), pnt_tr.Y(), pnt_tr.Z()])

        # Triangles (1-based indices)
        for i in range(1, triangulation.NbTriangles() + 1):
            tri = triangles.Value(i)
            i1, i2, i3 = tri.Get()
            # Convert naar 0-based + offset
            faces.append([
                v_offset + (i1 - 1),
                v_offset + (i2 - 1),
                v_offset + (i3 - 1),
            ])

    if not vertices or not faces:
        raise RuntimeError("No triangulation data available for shape")

    v_np = np.array(vertices, dtype=float)
    f_np = np.array(faces, dtype=int)

    tri_mesh = trimesh.Trimesh(vertices=v_np, faces=f_np, process=False)
    glb_bytes = trimesh.exchange.gltf.export_glb(tri_mesh)

    glb_b64 = base64.b64encode(glb_bytes).decode("ascii")
    return glb_b64


# ============================
# Routes
# ============================

@app.get("/")
def health():
    return {"status": "ok"}


@app.post("/upload-part")
async def upload_part(
    file: UploadFile = File(...),
    material: str = Form("steel"),
):
    """
    Analyse-only endpoint: bbox, afmetingen, volume, gewicht.
    """
    # 1. Save temp
    ext = os.path.splitext(file.filename)[1].lower()
    temp_name = f"{uuid.uuid4()}{ext}"
    temp_path = f"/tmp/{temp_name}"

    with open(temp_path, "wb") as f:
        f.write(await file.read())

    # 2. Analyse
    try:
        shape, result = analyze_step_file(temp_path, material)
    except Exception as e:
        return JSONResponse(
            {"error": f"STEP analysis failed: {str(e)}"},
            status_code=400,
        )

    # 3. Response
    return {
        "fileName": file.filename,
        "material": material,
        "tempPath": temp_path,
        **result,
    }


@app.post("/upload-part-with-mesh")
async def upload_part_with_mesh(
    file: UploadFile = File(...),
    material: str = Form("steel"),
):
    """
    Analyse + GLB-mesh (base64).
    Ideaal voor Three.js / Lovable:
    - je krijgt dimensies, volume, gewicht
    - én een GLB als base64-string.
    """
    # 1. Save temp
    ext = os.path.splitext(file.filename)[1].lower()
    temp_name = f"{uuid.uuid4()}{ext}"
    temp_path = f"/tmp/{temp_name}"

    with open(temp_path, "wb") as f:
        f.write(await file.read())

    # 2. Analyse
    try:
        shape, result = analyze_step_file(temp_path, material)
    except Exception as e:
        return JSONResponse(
            {"error": f"STEP analysis failed: {str(e)}"},
            status_code=400,
        )

    # 3. Mesh export
    try:
        glb_b64 = shape_to_glb_base64(shape)
    except Exception as e:
        return JSONResponse(
            {"error": f"Mesh export failed: {str(e)}"},
            status_code=500,
        )

    # 4. Response
    return {
        "fileName": file.filename,
        "material": material,
        "tempPath": temp_path,
        **result,
        "mesh": {
            "format": "glb",
            "encoding": "base64",
            "data": glb_b64,
        },
    }
