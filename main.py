from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uuid
import os

# OCC imports
from OCP.STEPControl import STEPControl_Reader
from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box
from OCP.StlAPI import StlAPI_Writer
from OCP.TopoDS import TopoDS_Shape
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID

app = FastAPI()

# -----------------------
# ENABLE CORS FOR LOVABLE
# -----------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # <-- allow frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def health():
    return {"status": "ok"}

# -----------------------
# HELPERS
# -----------------------

def load_step_shape(path: str) -> TopoDS_Shape:
    reader = STEPControl_Reader()
    status = reader.ReadFile(path)

    if status != 1:
        raise RuntimeError("STEP could not be read")

    reader.TransferRoots()
    shape = reader.OneShape()
    return shape

def compute_bbox(shape: TopoDS_Shape):
    bbox = Bnd_Box()
    bbox.SetGap(0)

    BRepBndLib.Add(shape, bbox)

    xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
    return {
        "xmin": xmin,
        "xmax": xmax,
        "ymin": ymin,
        "ymax": ymax,
        "zmin": zmin,
        "zmax": zmax
    }

def compute_volume(shape: TopoDS_Shape):
    from OCP.GProp import GProp_GProps
    from OCP.BRepGProp import BRepGProp

    props = GProp_GProps()
    BRepGProp.VolumeProperties(shape, props)
    return props.Mass()  # mm3

# -----------------------
# UPLOAD WITHOUT MESH (ONLY PROPERTIES)
# -----------------------

@app.post("/upload-part")
async def upload_part(
    file: UploadFile = File(...),
    material: str = Form("steel")
):
    ext = os.path.splitext(file.filename)[1].lower()
    temp_name = f"{uuid.uuid4()}{ext}"
    temp_path = f"/tmp/{temp_name}"

    with open(temp_path, "wb") as f:
        f.write(await file.read())

    try:
        shape = load_step_shape(temp_path)
    except Exception as e:
        return JSONResponse({"error": f"STEP load failed: {str(e)}"}, status_code=500)

    bbox = compute_bbox(shape)
    length = bbox["xmax"] - bbox["xmin"]
    width = bbox["ymax"] - bbox["ymin"]
    height = bbox["zmax"] - bbox["zmin"]

    volume_mm3 = compute_volume(shape)
    volume_m3 = volume_mm3 / 1e9
    weight_kg = volume_m3 * 7850  # steel density approx

    return {
        "fileName": file.filename,
        "material": material,
        "tempPath": temp_path,
        "rawBoundingBox": bbox,
        "partDimensions_mm": {
            "length": round(length, 3),
            "width": round(width, 3),
            "height": round(height, 3),
        },
        "partData": {
            "length_mm": round(length, 3),
            "width_mm": round(width, 3),
            "height_mm": round(height, 3),
            "volume_mm3": round(volume_mm3, 3),
            "volume_m3": round(volume_m3, 6),
            "weight_kg": round(weight_kg, 4)
        }
    }

# -----------------------
# UPLOAD + MESH EXPORT (GLB/STL)
# -----------------------

@app.post("/upload-part-with-mesh")
async def upload_part_with_mesh(
    file: UploadFile = File(...),
    material: str = Form("steel")
):
    ext = os.path.splitext(file.filename)[1].lower()
    temp_name = f"{uuid.uuid4()}{ext}"
    temp_path = f"/tmp/{temp_name}"

    with open(temp_path, "wb") as f:
        f.write(await file.read())

    try:
        shape = load_step_shape(temp_path)
    except Exception as e:
        return JSONResponse({"error": f"STEP load failed: {str(e)}"}, status_code=500)

    # Compute properties
    bbox = compute_bbox(shape)
    length = bbox["xmax"] - bbox["xmin"]
    width = bbox["ymax"] - bbox["ymin"]
    height = bbox["zmax"] - bbox["zmin"]
    volume_mm3 = compute_volume(shape)
    volume_m3 = volume_mm3 / 1e9
    weight_kg = volume_m3 * 7850

    # Export STL (can be converted to GLB client-side)
    stl_path = f"/tmp/{uuid.uuid4()}.stl"
    try:
        writer = StlAPI_Writer()
        writer.Write(shape, stl_path)
    except Exception as e:
        return JSONResponse({"error": f"Mesh export failed: {str(e)}"}, status_code=500)

    return {
        "fileName": file.filename,
        "material": material,
        "tempPath": temp_path,
        "stlPath": stl_path,
        "rawBoundingBox": bbox,
        "dimensions_mm": {
            "length": round(length, 3),
            "width": round(width, 3),
            "height": round(height, 3)
        },
        "volume_mm3": round(volume_mm3, 3),
        "volume_m3": round(volume_m3, 6),
        "weight_kg": round(weight_kg, 4)
    }

