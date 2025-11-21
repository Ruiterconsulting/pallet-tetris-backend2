from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uuid
import os

# OCC imports (pythonocc-core 7.7.0)
from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.BRepBndLib import brepbndlib_Add
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.GProp import GProp_GProps
from OCC.Core.BRepGProp import brepgprop_VolumeProperties
from OCC.Core.StlAPI import StlAPI_Writer
from OCC.Core.TopoDS import TopoDS_Shape

app = FastAPI()

# Allow frontend (Lovable) to fetch STL
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health():
    return {"status": "ok"}


# ------------------------------
# STEP loading
# ------------------------------
def load_step_shape(path: str) -> TopoDS_Shape:
    reader = STEPControl_Reader()
    status = reader.ReadFile(path)

    if status != 1:
        raise RuntimeError(f"Failed to read STEP file: {path}")

    reader.TransferRoots()
    return reader.OneShape()


# ------------------------------
# Bounding Box
# ------------------------------
def compute_bbox(shape: TopoDS_Shape):
    bbox = Bnd_Box()
    brepbndlib_Add(shape, bbox)

    xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
    return {
        "xmin": xmin,
        "xmax": xmax,
        "ymin": ymin,
        "ymax": ymax,
        "zmin": zmin,
        "zmax": zmax,
    }


# ------------------------------
# Volume
# ------------------------------
def compute_volume(shape: TopoDS_Shape):
    props = GProp_GProps()
    brepgprop_VolumeProperties(shape, props)
    return props.Mass()


# ------------------------------
# Upload + Analyze + Export STL
# ------------------------------
@app.post("/upload-part-with-mesh")
async def upload_part_with_mesh(
    file: UploadFile = File(...),
    material: str = Form("steel")
):
    # Save file temporary
    ext = os.path.splitext(file.filename)[1].lower()
    temp_name = f"{uuid.uuid4()}{ext}"
    temp_path = f"/tmp/{temp_name}"

    with open(temp_path, "wb") as f:
        f.write(await file.read())

    # Load STEP shape
    try:
        shape = load_step_shape(temp_path)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

    # Compute bbox + dims
    bbox = compute_bbox(shape)
    length = bbox["xmax"] - bbox["xmin"]
    width = bbox["ymax"] - bbox["ymin"]
    height = bbox["zmax"] - bbox["zmin"]

    # Volume + weight
    volume_mm3 = compute_volume(shape)
    volume_m3 = volume_mm3 / 1e9

    # Assume steel density 7850 kg/m3
    weight_kg = volume_m3 * 7850

    # Export STL for viewer
    stl_path = f"/tmp/{uuid.uuid4()}.stl"
    writer = StlAPI_Writer()
    writer.Write(shape, stl_path)

    # Return metadata
    return {
        "fileName": file.filename,
        "material": material,
        "tempPath": temp_path,
        "stlPath": stl_path,
        "rawBoundingBox": bbox,
        "dimensions_mm": {
            "length": length,
            "width": width,
            "height": height
        },
        "volume_mm3": volume_mm3,
        "volume_m3": volume_m3,
        "weight_kg": weight_kg
    }


# ------------------------------
# STL Download Endpoint
# ------------------------------
@app.get("/download-stl")
def download_stl(path: str):
    if not os.path.exists(path):
        return JSONResponse({"error": "File not found"}, status_code=404)

    return FileResponse(
        path,
        media_type="model/stl",
        filename=os.path.basename(path)
    )
