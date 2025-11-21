FROM python:3.11-bullseye

# System libs required for OpenCascade
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libxext6 \
    libsm6 \
    libxrender1 \
    libxcursor1 \
    libxrandr2 \
    libxinerama1 \
    libfontconfig1 \
    libfreetype6 \
    libxkbcommon0 \
    libglu1-mesa \
    && apt-get clean

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /app
COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
