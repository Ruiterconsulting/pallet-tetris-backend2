FROM continuumio/miniconda3:23.3.1-0

# Create a conda environment
RUN conda create -y -n occ_env python=3.9

# Use that env by default
SHELL ["conda", "run", "-n", "occ_env", "/bin/bash", "-c"]

# Install OpenCascade + pythonocc-core 7.6 (stable)
RUN conda install -y -c conda-forge occt=7.6.0 pythonocc-core=7.6.3

# Install FastAPI deps
RUN pip install fastapi uvicorn python-multipart numpy

WORKDIR /app
COPY . .

EXPOSE 8000

CMD ["conda", "run", "--no-capture-output", "-n", "occ_env", \
     "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
