FROM python:3.11-bullseye

# get portaudio and ffmpeg
RUN apt-get update \
        && apt-get install -y libportaudio2 libportaudiocpp0 portaudio19-dev libasound-dev libsndfile1-dev ffmpeg \
        && apt-get clean

RUN pip install vocode
