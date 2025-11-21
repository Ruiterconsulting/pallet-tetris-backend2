FROM continuumio/miniconda3:23.11.0-0

# Create environment
RUN conda create -y -n occ_env python=3.10

# All commands use the env
SHELL ["conda", "run", "-n", "occ_env", "/bin/bash", "-c"]

# Install OpenCascade + pythonocc-core
RUN conda install -y -c conda-forge occt=7.7.0 pythonocc-core=7.7.0

# FastAPI deps
RUN pip install fastapi uvicorn python-multipart numpy

WORKDIR /app
COPY . .

EXPOSE 8000

CMD ["conda", "run", "--no-capture-output", "-n", "occ_env", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
