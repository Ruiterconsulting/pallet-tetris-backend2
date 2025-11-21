FROM python:3.10-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libxcb1 \
    && apt-get clean

# Install Python packages
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    python-multipart \
    numpy \
    pyocct

WORKDIR /app
COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
