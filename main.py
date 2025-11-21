from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
import uuid
import os

# OpenCascade imports
from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.BRepBndLib import brepbndlib_Add
from OCC.Core.GProp import GProp_GProps
from OCC.Core.BRepGProp import brepgprop_VolumeProperties

app = FastAPI()


@app.get("/")
def health():
    return {"status": "ok"}


@app.post("/upload-part")
async def upload_part(
    file: UploadFile = File(...),
    material: str = Form("steel")
):
    # ============================
    # 1. Save temp file
    # ============================
    ext = os.path.splitext(file.filename)[1].lower()
    temp_name = f"{uuid.uuid4()}{ext}"
    temp_path = f"/tmp/{temp_name}"

    with open(temp_path, "wb") as f:
        f.write(await file.read())

    # ============================
    # 2. Read STEP file with OCC
    # ============================
    reader = STEPControl_Reader()
    status = reader.ReadFile(temp_path)

    if status != 1:
        return JSONResponse(
            {"error": "Failed to read STEP file"},
            status_code=400
        )

    reader.TransferRoots()
    shape = reader.OneShape()

    # ============================
    # 3. Bounding box
    # ============================
    bbox = Bnd_Box()
    brepbndlib_Add(shape, bbox)

    xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()

    length = xmax - xmin
    width  = ymax - ymin
    height = zmax - zmin

    # ============================
    # 4. Volume calculation
    # ============================
    props = GProp_GProps()
    brepgprop_VolumeProperties(shape, props)
    volume = props.Mass()  # in cubic mm

    # ============================
    # 5. Weight calculation
    # ============================
    # densities in kg/m3
    densities = {
        "steel": 7850,
        "aluminum": 2700,
        "stainless": 8000,
        "copper": 8960
    }

    density = densities.get(material.lower(), 7850)

    # Convert mm^3 → m^3:
    volume_m3 = volume / 1_000_000_000

    weight = volume_m3 * density  # kg

    # ============================
    # 6. Return JSON
    # ============================
    return {
        "receivedFile": file.filename,
        "temporaryPath": temp_path,
        "material": material,
        "bbox": {
            "xmin": xmin, "xmax": xmax,
            "ymin": ymin, "ymax": ymax,
            "zmin": zmin, "zmax": zmax
        },
        "dimensions_mm": {
            "length": length,
            "width": width,
            "height": height
        },
        "volume_mm3": volume,
        "volume_m3": volume_m3,
        "weight_kg": weight
    }
