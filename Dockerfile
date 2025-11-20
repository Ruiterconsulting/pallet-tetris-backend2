FROM python:3.11

# Install system dependencies for OpenCascade
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    libgl1-mesa-dev \
    libglu1-mesa-dev \
    libxmu-dev \
    libxi-dev \
    freeglut3-dev \
    libfreetype6-dev \
    mesa-common-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install python dependencies (will install pythonocc-core)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
