import os
import uuid
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

import FreeCAD
import Part
import Mesh

app = FastAPI()

PUBLIC_DIR = "/app/public"
os.makedirs(PUBLIC_DIR, exist_ok=True)
app.mount("/public", StaticFiles(directory=PUBLIC_DIR), name="public")


@app.get("/")
def health():
    return {"status": "ok"}


@app.post("/upload-part")
async def upload_part(
    file: UploadFile = File(...),
    material: str = Form("steel")
):

    # Temp STEP
    ext = os.path.splitext(file.filename)[1].lower()
    step_temp = f"/tmp/{uuid.uuid4()}{ext}"

    with open(step_temp, "wb") as f:
        f.write(await file.read())

    # Load STEP
    doc = FreeCAD.newDocument()
    shape = doc.addObject("Part::Feature", "Shape")
    shape.Shape = Part.Shape()
    shape.Shape.read(step_temp)

    # Bounding box
    bbox = shape.Shape.BoundBox
    length = bbox.XLength
    width = bbox.YLength
    height = bbox.ZLength

    # Mesh → STL
    stl_name = f"{uuid.uuid4()}.stl"
    stl_path = f"{PUBLIC_DIR}/{stl_name}"

    mesh_obj = doc.addObject("Mesh::Feature", "mesh")
    mesh_obj.Mesh = Mesh.meshFromShape(
        shape.Shape,
        LinearDeflection=0.5,
        AngularDeflection=0.5
    )
    Mesh.export([mesh_obj], stl_path)

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
