FROM python:3.10-slim

# System dependencies required for OpenCascade
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libgl1 \
    libxext6 \
    libsm6 \
    libxrender1 \
    libx11-6 \
    libfontconfig1 \
    libglu1-mesa \
    && apt-get clean

# Install Python dependencies
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    python-multipart \
    numpy \
    OCP

WORKDIR /app
COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
