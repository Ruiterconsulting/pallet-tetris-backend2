from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse

import cadquery as cq
import tempfile
import os
import traceback


# ============================================================
# FastAPI setup
# ============================================================

app = FastAPI(title="Pallet Tetris Analyzer", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Helpers
# ============================================================

def ensure_step(filename: str):
    ext = (os.path.splitext(filename)[1] or "").lower()
    if ext not in [".step", ".stp"]:
        raise HTTPException(status_code=415, detail="Upload .STEP or .STP only")


# ============================================================
# Root endpoint
# ============================================================

@app.get("/")
def root():
    return {"message": "Pallet Tetris Analyzer live ✅"}


# ============================================================
# Download endpoint (for STL)
# ============================================================

@app.get("/download/{file_name}")
def download_file(file_name: str):
    full_path = f"/tmp/{file_name}"

    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(full_path, media_type="application/octet-stream", filename=file_name)


# ============================================================
# Analyze STEP
# ============================================================

@app.post("/analyze")
async def analyze_step(file: UploadFile = File(...)):
    tmp_step = None
    filename = file.filename

    try:
        ensure_step(filename)

        # --------------------------------------------------------
        # Save STEP into /tmp
        # --------------------------------------------------------
        with tempfile.NamedTemporaryFile(delete=False, suffix=".step", dir="/tmp") as t:
            t.write(await file.read())
            tmp_step = t.name

        # --------------------------------------------------------
        # Load STEP using CadQuery
        # --------------------------------------------------------
        model = cq.importers.importStep(tmp_step)
        shape = model.val()
        if shape is None or shape.isNull():
            raise RuntimeError("Imported STEP shape is null")

        # --------------------------------------------------------
        # Bounding box
        # --------------------------------------------------------
        bbox = shape.BoundingBox()

        raw_box = {
            "xmin": float(bbox.xmin),
            "xmax": float(bbox.xmax),
            "ymin": float(bbox.ymin),
            "ymax": float(bbox.ymax),
            "zmin": float(bbox.zmin),
            "zmax": float(bbox.zmax),
        }

        # Dimensions sorted
        dims_sorted = sorted(
            [float(bbox.xlen), float(bbox.ylen), float(bbox.zlen)],
            reverse=True
        )

        dimensions_mm = {
            "length": round(dims_sorted[0], 3),
            "width": round(dims_sorted[1], 3),
            "height": round(dims_sorted[2], 3),
        }

        # --------------------------------------------------------
        # Volume & Weight
        # --------------------------------------------------------
        try:
            volume_mm3 = float(shape.Volume())
        except Exception:
            volume_mm3 = None

        if volume_mm3:
            volume_m3 = volume_mm3 / 1_000_000_000
            weight_kg = round(volume_m3 * 7850, 4)
        else:
            volume_m3 = None
            weight_kg = None

        # --------------------------------------------------------
        # Export STL to /tmp
        # --------------------------------------------------------
        stl_name = os.path.basename(tmp_step).replace(".step", ".stl")
        tmp_stl_path = f"/tmp/{stl_name}"

        try:
            cq.exporters.export(shape, tmp_stl_path, "STL")
        except Exception as e:
            print("⚠️ STL export failed:", e)
            tmp_stl_path = None

        stl_url = (
            f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/download/{stl_name}"
            if tmp_stl_path
            else None
        )

        # --------------------------------------------------------
        # JSON Response
        # --------------------------------------------------------
        return JSONResponse(
            content={
                "fileName": filename,
                "material": "steel",
                "dimensions_mm": dimensions_mm,
                "rawBoundingBox": raw_box,
                "volume_mm3": round(volume_mm3, 3) if volume_mm3 else None,
                "volume_m3": round(volume_m3, 9) if volume_m3 else None,
                "weight_kg": weight_kg,
                "stlURL": stl_url,
            }
        )

    except Exception as e:
        tb = traceback.format_exc(limit=12)
        print("❌ Analysis failed:", e)
        return JSONResponse(
            status_code=500,
            content={
                "error": str(e),
                "trace": tb,
                "fileName": filename,
            },
        )

    finally:
        # Clean STEP (STL blijft beschikbaar voor download)
        try:
            if tmp_step and os.path.exists(tmp_step):
                os.remove(tmp_step)
        except Exception:
            pass
