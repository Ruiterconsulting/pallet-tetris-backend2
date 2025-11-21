FROM python:3.11-slim

# Install FreeCAD + dependencies
RUN apt-get update && apt-get install -y \
    freecad \
    python3-pyside2.qtcore \
    python3-pyside2.qtgui \
    python3-pyside2.qtnetwork \
    python3-pyside2.qtwidgets \
    python3-pyside2.qtx11extras \
    && apt-get clean

# Python deps
RUN pip install fastapi uvicorn python-multipart numpy

WORKDIR /app
COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
