FROM continuumio/miniconda3:latest

# Create environment
RUN conda create -y -n occ_env python=3.10

# Activate env by default
SHELL ["conda", "run", "-n", "occ_env", "/bin/bash", "-c"]

# Install OCC + dependencies
RUN conda install -y -c conda-forge occ==0.19.4 occt=7.7.0 pythonocc-core=7.7.0

# Backend deps
RUN conda install -y -c conda-forge fastapi uvicorn python-multipart numpy

WORKDIR /app
COPY . .

EXPOSE 8000

CMD ["conda", "run", "--no-capture-output", "-n", "occ_env", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
