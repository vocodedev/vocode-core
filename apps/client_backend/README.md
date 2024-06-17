# client_backend

## Docker

1. Set up the configuration for your agent in `main.py`.
2. Set up an .env file using the template

```
cp .env.template .env
```

Fill in your API keys into .env

3. Build the Docker image

```bash
docker build -t vocode-client-backend .
```

4. Run the image and forward the port.

```bash
docker run --env-file=.env -p 3000:3000 -t vocode-client-backend
```

Now you have a client backend hosted at localhost:3000 to pass into the Vocode React SDK. You'll likely need to tunnel port 3000 to ngrok / host your server in order to use it in the React SDK.

## Non-docker setup

`main.py` just sets up a FastAPI server, so you can just run it with uvicorn:

```
uvicorn main:app
```
