FROM python:3.10

# System dependencies for OpenCascade + OCP
RUN apt-get update && apt-get install -y \
    libgl1-mesa-dev \
    libglu1-mesa \
    libx11-dev \
    libxext-dev \
    libsm6 \
    libxrender1 \
    libfontconfig1 \
    && apt-get clean

# Python dependencies
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
