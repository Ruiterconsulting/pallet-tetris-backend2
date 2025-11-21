from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uuid
import os
import numpy as np

from OCP.STEPControl import STEPControl_Reader
from OCP.IFSelect import IFSelect_RetDone
from OCP.StlAPI import StlAPI_Writer
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib

app = FastAPI()

# Public folder for STL files
PUBLIC_DIR = "/app/public"
os.makedirs(PUBLIC_DIR, exist_ok=True)

# Serve /public/ via HTTP
app.mount("/public", StaticFiles(directory=PUBLIC_DIR), name="public")


@app.get("/")
def health():
    return {"status": "ok"}


@app.post("/upload-part")
async def upload_part(
    file: UploadFile = File(...),
    material: str = Form("steel")
):
    ext = os.path.splitext(file.filename)[1].lower()
    temp_name = f"{uuid.uuid4()}{ext}"
    temp_path = f"/tmp/{temp_name}"

    # Save uploaded file to /tmp
    with open(temp_path, "wb") as f:
        f.write(await file.read())

    # STEP → Shape
    reader = STEPControl_Reader()
    status = reader.ReadFile(temp_path)

    if status != IFSelect_RetDone:
        return JSONResponse({"error": "STEP read failed"}, status_code=400)

    reader.TransferRoots()
    shape = reader.OneShape()

    # Bounding box
    bbox = Bnd_Box()
    BRepBndLib.Add(shape, bbox)

    xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
    length = float(xmax - xmin)
    width = float(ymax - ymin)
    height = float(zmax - zmin)

    # Mesh → STL
    stl_name = f"{uuid.uuid4()}.stl"
    stl_path = os.path.join(PUBLIC_DIR, stl_name)

    writer = StlAPI_Writer()
    writer.Write(shape, stl_path)

    # Build response
    stl_url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/public/{stl_name}"

    return {
        "fileName": file.filename,
        "material": material,
        "dimensions_mm": {
            "length": length,
            "width": width,
            "height": height
        },
        "stlUrl": stl_url
    }
