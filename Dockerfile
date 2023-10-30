FROM python:3.9-bullseye

# get portaudio and ffmpeg
RUN apt-get update \
        && apt-get install libportaudio2 libportaudiocpp0 portaudio19-dev libasound-dev libsndfile1-dev -y
RUN apt-get -y update
RUN apt-get -y upgrade
RUN apt-get install -y ffmpeg

WORKDIR /code
COPY pyproject.toml pyproject.toml
COPY /apps/client_backend/ apps/client_backend/
COPY /vocode/ vocode/
COPY README.md README.md

RUN pip install --upgrade pip
RUN pip install --no-cache-dir --upgrade poetry
RUN poetry config virtualenvs.create false
RUN poetry install --only main --no-interaction --no-ansi

WORKDIR /code/apps/client_backend
RUN poetry install --only main --no-interaction --no-ansi

# Charlie added
# COPY ../../vocode/requirements.txt /vocode/requirements.txt
# RUN pip install -r /vocode/requirements.txt

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
