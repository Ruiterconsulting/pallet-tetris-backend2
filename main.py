import os
import uuid
import subprocess
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

PUBLIC_DIR = "/app/public"
os.makedirs(PUBLIC_DIR, exist_ok=True)
app.mount("/public", StaticFiles(directory=PUBLIC_DIR), name="public")


@app.post("/upload-part")
async def upload_part(file: UploadFile = File(...), material: str = Form("steel")):

    # Save STEP temporarily
    ext = os.path.splitext(file.filename)[1].lower()
    step_path = f"/tmp/{uuid.uuid4()}{ext}"

    with open(step_path, "wb") as f:
        f.write(await file.read())

    # STL output
    stl_name = f"{uuid.uuid4()}.stl"
    stl_path = f"{PUBLIC_DIR}/{stl_name}"

    # Use OpenCascade CLI to convert STEP → STL
    result = subprocess.run(
        ["occ-step2stl", step_path, stl_path],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        return {"error": "STEP → STL failed", "details": result.stderr}

    # Public URL
    host = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    stl_url = f"https://{host}/public/{stl_name}"

    return {
        "fileName": file.filename,
        "material": material,
        "stlUrl": stl_url,
        "message": "Conversion OK"
    }
