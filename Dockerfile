FROM python:3.9-bullseye

# Install system dependencies
RUN apt-get update \
    && apt-get install -y libportaudio2 libportaudiocpp0 portaudio19-dev libasound-dev libsndfile1-dev ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip
RUN pip install --no-cache-dir --upgrade poetry
RUN poetry config virtualenvs.create false

# Copy only dependency-related files to cache them
WORKDIR /code
COPY pyproject.toml poetry.lock /code/
COPY /apps/client_backend/pyproject.toml /code/apps/client_backend/pyproject.toml
COPY /apps/client_backend/poetry.lock /code/apps/client_backend/poetry.lock

# Install top-level dependencies
RUN poetry install --only main --no-interaction --no-ansi

# Copy vocode module and install client backend dependencies
COPY /vocode/ /code/vocode/
COPY README.md /code/README.md

WORKDIR /code/apps/client_backend
RUN poetry install --only main --no-interaction --no-ansi
WORKDIR /code

# Copy all other files
COPY /apps/client_backend/ /code/apps/client_backend/

WORKDIR /code/apps/client_backend
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
