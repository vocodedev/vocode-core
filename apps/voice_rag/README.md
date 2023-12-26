# voice_rag

## Docker

1. Set up the configuration for your agent in `main.py`.
2. Set up an .env file using the template

```
cp .env.template .env
```

Fill in your API keys into .env

3. Build the Docker image

```bash
docker build --build-arg BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ') \
             --build-arg VCS_REF=$(git rev-parse --short HEAD) \
             --build-arg VERSION=0.1.0 \
             -t vocode/vocode-voice-rag:0.1.0 .
```

4. Run the image and forward the port.

```bash
docker run --env-file=.env -p 3000:3000 -t vocode/vocode-voice-rag
```

Now you have a client backend hosted at localhost:3000 to pass into the Vocode React SDK. You'll likely need to tunnel port 3000 to ngrok / host your server in order to use it in the React SDK.

## Non-docker setup

`main.py` just sets up a FastAPI server, so you can just run it with uvicorn:

```
uvicorn main:app
```
