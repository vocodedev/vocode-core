FROM python:3.9-bullseye

# get portaudio and ffmpeg
RUN apt-get update \
        && apt-get install libportaudio2 libportaudiocpp0 portaudio19-dev libasound-dev libsndfile1-dev -y
RUN apt-get -y update
RUN apt-get -y upgrade
RUN apt-get install -y ffmpeg

WORKDIR /code
# COPY /apps/client_backend/pyproject.toml pyproject.toml
COPY pyproject.toml pyproject.toml
COPY /apps/client_backend/poetry.lock poetry.lock
RUN pip install --no-cache-dir --upgrade poetry
RUN poetry config virtualenvs.create false
RUN poetry install --no-dev --no-interaction --no-ansi
COPY /apps/client_backend/main.py main.py
COPY /vocode/ vocode/
COPY /README.md README.md
RUN pip install -e .

# Charlie added
# COPY ../../vocode/requirements.txt /vocode/requirements.txt
# RUN pip install -r /vocode/requirements.txt

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
