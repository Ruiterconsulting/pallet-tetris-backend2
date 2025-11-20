from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
import uuid
import os

app = FastAPI()

@app.get("/")
def health():
    return {"status": "ok"}

@app.post("/upload-part")
async def upload_part(
    file: UploadFile = File(...),
    material: str = Form("steel")
):
    # maak tijdelijk bestand op server
    ext = os.path.splitext(file.filename)[1].lower()
    temp_name = f"{uuid.uuid4()}{ext}"
    temp_path = f"/tmp/{temp_name}"

    with open(temp_path, "wb") as f:
        f.write(await file.read())

    # dit is een dummy response (later vervangen door CAD-gegevens)
    return JSONResponse({
        "receivedFile": file.filename,
        "temporaryPath": temp_path,
        "material": material,
        "message": "File upload successful (dummy response)."
    })
  
