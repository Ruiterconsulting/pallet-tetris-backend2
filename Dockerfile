FROM continuumio/miniconda3

# Create conda environment
RUN conda create -n occ python=3.11 -y
RUN echo "source activate occ" > ~/.bashrc
ENV PATH /opt/conda/envs/occ/bin:$PATH

# Install OpenCascade via conda-forge
RUN conda install -n occ -c conda-forge occt=7.7.0 -y

# Install pythonocc-core + FastAPI stack + trimesh
RUN conda install -n occ -c conda-forge \
    pythonocc-core=7.7.0 \
    fastapi \
    uvicorn \
    python-multipart \
    numpy \
    trimesh \
    -y

WORKDIR /app
COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
