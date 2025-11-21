FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    libxcb1 \
    libx11-6 \
    && apt-get clean

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
