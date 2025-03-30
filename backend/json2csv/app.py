from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import os
from pathlib import Path
import shutil
import uuid
from media_converter import MediaConverter

app = FastAPI(title="Media Converter")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Create uploads directory if it doesn't exist
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@app.get("/")
async def read_root():
    return FileResponse("templates/index.html")

@app.post("/convert")
async def convert_file(file: UploadFile, output_format: str):
    try:
        # Generate unique filename
        temp_file = UPLOAD_DIR / f"{uuid.uuid4()}{Path(file.filename).suffix}"
        output_file = UPLOAD_DIR / f"{uuid.uuid4()}.{output_format}"

        # Save uploaded file
        with temp_file.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Convert file
        if Path(file.filename).suffix[1:].lower() in ['jpg', 'jpeg', 'png', 'webp']:
            output_path = MediaConverter.convert_image(str(temp_file), output_format)
        else:
            output_path = MediaConverter.convert_video(str(temp_file), output_format)

        # Read the converted file and prepare for download
        return FileResponse(
            path=output_path,
            filename=f"converted.{output_format}",
            media_type="application/octet-stream"
        )

    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"error": str(e)}
        )

    finally:
        # Cleanup
        if temp_file.exists():
            temp_file.unlink()
        file.file.close()

@app.get("/formats")
async def get_formats():
    return {
        "image": ["jpg", "png", "webp"],
        "video": ["mp4", "avi", "wmv"]
    }
