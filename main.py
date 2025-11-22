from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import cadquery as cq
import tempfile
import os
import traceback
import math

app = FastAPI(title="Pallet Tetris Analyzer", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def ensure_step(filename: str):
    ext = (os.path.splitext(filename)[1] or "").lower()
    if ext not in [".step", ".stp"]:
        raise HTTPException(status_code=415, detail="Upload .STEP or .STP only")


@app.get("/")
def root():
    return {"message": "Pallet Tetris analyzer live ✅"}


@app.post("/analyze")
async def analyze_step(file: UploadFile = File(...)):
    tmp_step = tmp_stl = None
    filename = file.filename

    try:
        ensure_step(filename)

        # 1) STEP naar /tmp
        with tempfile.NamedTemporaryFile(delete=False, suffix=".step") as t:
            t.write(await file.read())
            tmp_step = t.name

        # 2) STEP inlezen via cadquery
        model = cq.importers.importStep(tmp_step)
        shape = model.val()
        if shape is None or shape.isNull():
            raise RuntimeError("Imported STEP shape is null")

        # 3) Bounding box
        bbox = shape.BoundingBox()
        raw_box = {
            "xmin": float(bbox.xmin),
            "xmax": float(bbox.xmax),
            "ymin": float(bbox.ymin),
            "ymax": float(bbox.ymax),
            "zmin": float(bbox.zmin),
            "zmax": float(bbox.zmax),
        }

        # Afmetingen (mm)
        x_len = float(bbox.xlen)
        y_len = float(bbox.ylen)
        z_len = float(bbox.zlen)

        # Sorteer: grootste = length, middelste = width, kleinste = height
        dims_sorted = sorted([x_len, y_len, z_len], reverse=True)
        dimensions_mm = {
            "length": round(dims_sorted[0], 3),
            "width": round(dims_sorted[1], 3),
            "height": round(dims_sorted[2], 3),
        }

        # 4) Volume + gewicht
        try:
            volume_mm3 = float(shape.Volume())
        except Exception:
            volume_mm3 = None

        if volume_mm3 is not None:
            volume_m3 = volume_mm3 / 1_000_000_000.0  # mm³ → m³
            # simpele aanname: staal ~7850 kg/m³
            density_steel = 7850.0
            weight_kg = volume_m3 * density_steel
            weight_kg = round(weight_kg, 4)
        else:
            volume_m3 = None
            weight_kg = None

        # 5) (optioneel) STL export – alleen als je deze later nodig hebt
        tmp_stl = tmp_step.replace(".step", ".stl")
        try:
            cq.exporters.export(shape, tmp_stl, "STL")
        except Exception as e:
            print("⚠️ STL export failed:", e)
            tmp_stl = None

        # Voor nu geen Supabase in deze versie – alleen metadata terug
        payload = {
            "fileName": filename,
            "material": "steel",  # voorlopig vast; later via form/input
            "tempPath": tmp_step,  # alleen intern nuttig, maar laat hem staan als je hem al gebruikt
            "stlPath": tmp_stl,
            "rawBoundingBox": raw_box,
            "dimensions_mm": dimensions_mm,
            "volume_mm3": round(volume_mm3, 3) if volume_mm3 is not None else None,
            "volume_m3": round(volume_m3, 9) if volume_m3 is not None else None,
            "weight_kg": weight_kg,
        }

        return JSONResponse(content=payload)

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
        # alleen de STEP opruimen; STL kun je evt. laten staan zolang je hem niet gebruikt
        try:
            if tmp_step and os.path.exists(tmp_step):
                os.remove(tmp_step)
        except Exception:
            pass
