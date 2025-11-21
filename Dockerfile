FROM debian:12

# Install OCCT CLI tools + Python + pip
RUN apt-get update && apt-get install -y \
    occt-tools \
    python3 \
    python3-pip \
    && apt-get clean

# Python deps
RUN pip install fastapi uvicorn python-multipart numpy

WORKDIR /app
COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
