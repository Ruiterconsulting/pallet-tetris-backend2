from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
import uuid
import os
import base64

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
from OCC.Core.TopoDS import topods_Face

app = FastAPI()


def round_f(x, n=3):
    return round(float(x), n)


def analyze_step_file(step_path: str, material: str):
    reader = STEPControl_Reader()
    status = reader.ReadFile(step_path)

    if status != 1:
        raise RuntimeError("Failed to read STEP file")

    reader.TransferRoots()
    shape = reader.OneShape()

    bbox = Bnd_Box()
    brepbndlib_Add(shape, bbox)
    xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()

    length = xmax - xmin
    width = ymax - ymin
    height = zmax - zmin

    props = GProp_GProps()
    brepgprop_VolumeProperties(shape, props)
    volume_mm3 = props.Mass()

    densities = {"steel": 7850, "aluminum": 2700, "stainless": 8000, "copper": 8960}
    density = densities.get(material.lower(), 7850)

    volume_m3 = volume_mm3 / 1_000_000_000.0
    weight_kg = volume_m3 * density

    result = {
        "rawBoundingBox": {
            "xmin": xmin, "xmax": xmax,
            "ymin": ymin, "ymax": ymax,
            "zmin": zmin, "zmax": zmax
        },
        "partDimensions_mm": {
            "length": round_f(length),
            "width": round_f(width),
            "height": round_f(height)
        },
        "partData": {
            "length_mm": round_f(length),
            "width_mm": round_f(width),
            "height_mm": round_f(height),
            "volume_mm3": round_f(volume_mm3, 3),
            "volume_m3": round_f(volume_m3, 9),
            "weight_kg": round_f(weight_kg, 4)
        }
    }

    return shape, result


def shape_to_glb_base64(shape):
    mesh = BRepMesh_IncrementalMesh(shape, 0.5, True)
    mesh.Perform()

    vertices = []
    faces = []

    exp = TopExp_Explorer(shape, TopAbs_FACE)

    while exp.More():
        face = topods_Face(exp.Current())
        loc = TopLoc_Location()
        triangulation = BRep_Tool.Triangulation(face, loc)

        if triangulation is not None:
            trsf = loc.Transformation()

            # --- Correcte API voor OCC 7.7.0 ---
            nb_nodes = triangulation.NbNodes()
            nb_tris = triangulation.NbTriangles()

            v_offset = len(vertices)

            # Nodes ophalen
            for i in range(1, nb_nodes + 1):
                pnt = triangulation.Node(i)
                pnt_tr = pnt.Transformed(trsf)
                vertices.append([pnt_tr.X(), pnt_tr.Y(), pnt_tr.Z()])

            # Triangles ophalen
            for t in range(1, nb_tris + 1):
                tri = triangulation.Triangle(t)
                i1, i2, i3 = tri.Get()
                faces.append([
                    v_offset + (i1 - 1),
                    v_offset + (i2 - 1),
                    v_offset + (i3 - 1),
                ])

        exp.Next()

    if not vertices or not faces:
        raise RuntimeError("No triangulation data available")

    vertices_np = np.array(vertices, float)
    faces_np = np.array(faces, int)

    m = trimesh.Trimesh(vertices=vertices_np, faces=faces_np, process=False)
    glb_bytes = trimesh.exchange.gltf.export_glb(m)

    return base64.b64encode(glb_bytes).decode("ascii")


@app.post("/upload-part-with-mesh")
async def upload_part_with_mesh(
    file: UploadFile = File(...),
    material: str = Form("steel"),
):
    ext = os.path.splitext(file.filename)[1].lower()
    temp_name = f"{uuid.uuid4()}{ext}"
    temp_path = f"/tmp/{temp_name}"

    with open(temp_path, "wb") as f:
        f.write(await file.read())

    try:
        shape, result = analyze_step_file(temp_path, material)
    except Exception as e:
        return JSONResponse({"error": f"STEP analysis failed: {str(e)}"}, 400)

    try:
        glb = shape_to_glb_base64(shape)
    except Exception as e:
        return JSONResponse({"error": f"Mesh export failed: {str(e)}"}, 500)

    return {
        "fileName": file.filename,
        "material": material,
        "mesh": {
            "format": "glb",
            "encoding": "base64",
            "data": glb
        },
        **result
    }
