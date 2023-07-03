FROM python:3.9-bullseye

# get portaudio and ffmpeg
RUN apt-get update \
        && apt-get install libportaudio2 libportaudiocpp0 portaudio19-dev libasound-dev libsndfile1-dev -y
RUN apt-get -y update
RUN apt-get -y upgrade
RUN apt-get install -y ffmpeg

WORKDIR /code
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r requirements.txt
COPY main.py /code/main.py
COPY speller_agent.py /code/speller_agent.py

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3000"]