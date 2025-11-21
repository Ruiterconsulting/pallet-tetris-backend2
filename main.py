from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uuid
import os

# Correct OCC imports
from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.BRepBndLib import brepbndlib_Add
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.gp import gp_Pnt
from OCC.Core.GProp import GProp_GProps
from OCC.Core.BRepGProp import brepgprop_VolumeProperties
from OCC.Core.StlAPI import StlAPI_Writer
from OCC.Core.TopoDS import TopoDS_Shape

app = FastAPI()

# CORS for Lovable
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


def load_step_shape(path: str) -> TopoDS_Shape:
    reader = STEPControl_Reader()
    status = reader.ReadFile(path)

    if status != 1:
        raise RuntimeError("Failed to read STEP")

    reader.TransferRoots()
    return reader.OneShape()


def compute_bbox(shape: TopoDS_Shape):
    bbox = Bnd_Box()
    brepbndlib_Add(shape, bbox)

    xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
    return {
        "xmin": xmin, "xmax": xmax,
        "ymin": ymin, "ymax": ymax,
        "zmin": zmin, "zmax": zmax,
    }


def compute_volume(shape: TopoDS_Shape):
    props = GProp_GProps()
    brepgprop_VolumeProperties(shape, props)
    return props.Mass()


@app.post("/upload-part-with-mesh")
async def upload_part_with_mesh(
    file: UploadFile = File(...),
    material: str = Form("steel")
):
    # Save file
    ext = os.path.splitext(file.filename)[1].lower()
    temp_name = f"{uuid.uuid4()}{ext}"
    temp_path = f"/tmp/{temp_name}"

    with open(temp_path, "wb") as f:
        f.write(await file.read())

    # Load shape
    try:
        shape = load_step_shape(temp_path)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

    # Compute metrics
    bbox = compute_bbox(shape)
    length = bbox["xmax"] - bbox["xmin"]
    width = bbox["ymax"] - bbox["ymin"]
    height = bbox["zmax"] - bbox["zmin"]

    volume_mm3 = compute_volume(shape)
    volume_m3 = volume_mm3 / 1e9
    weight_kg = volume_m3 * 7850  # steel

    # Export mesh as STL
    stl_path = f"/tmp/{uuid.uuid4()}.stl"
    writer = StlAPI_Writer()
    writer.Write(shape, stl_path)

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
