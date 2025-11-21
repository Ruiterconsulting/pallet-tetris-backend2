from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uuid
import os
import numpy as np

from pyocct_system import init_occt_system
from ocp_tessellate import step_to_stl, BoundingBox

# Initialize OCCT (required by pyocct)
init_occt_system()

app = FastAPI()

# Public folder for STL files
PUBLIC_DIR = "/app/public"
os.makedirs(PUBLIC_DIR, exist_ok=True)

# Mount static folder
app.mount("/public", StaticFiles(directory=PUBLIC_DIR), name="public")


@app.get("/")
def health():
    return {"status": "ok"}


@app.post("/upload-part")
async def upload_part(
    file: UploadFile = File(...),
    material: str = Form("steel")
):
    # Save temp STEP file
    ext = os.path.splitext(file.filename)[1].lower()
    temp_name = f"{uuid.uuid4()}{ext}"
    temp_path = f"/tmp/{temp_name}"

    with open(temp_path, "wb") as f:
        f.write(await file.read())

    # Convert STEP → STL
    stl_name = f"{uuid.uuid4()}.stl"
    stl_path = f"{PUBLIC_DIR}/{stl_name}"

    success = step_to_stl(temp_path, stl_path, linear_deflection=0.5, angular_deflection=0.5)

    if not success:
        return JSONResponse({"error": "STEP conversion failed"}, status_code=400)

    # Bounding box
    bbox = BoundingBox.from_step(temp_path)
    dims = bbox.dimensions()  # (length, width, height)

    length, width, height = dims

    # Volume approximation from bounding box (not exact)
    volume_mm3 = length * width * height
    density = 7850  # steel kg/m3
    weight_kg = (volume_mm3 / 1e9) * density

    # Public STL URL
    external_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    stl_url = f"https://{external_host}/public/{stl_name}"

    return {
        "fileName": file.filename,
        "material": material,
        "dimensions_mm": {
            "length": length,
            "width": width,
            "height": height
        },
        "bbox_raw": bbox.bounds,
        "volume_mm3": volume_mm3,
        "weight_kg": weight_kg,
        "stlUrl": stl_url
    }
