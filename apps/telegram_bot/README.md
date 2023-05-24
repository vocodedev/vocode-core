# client_backend

## Docker

1. Set up the configuration for your telegram bot in `main.py`.
2. Set up an .env file using the template

```
cp .env.template .env
```

Fill in your API keys into .env

3. Build the Docker image

```bash
docker build -t vocode-telegram-bot .
```

4. Run the image and forward the port.

```bash
docker run --env-file=.env -p 3000:3000 -t vocode-telegram-bot
```

Now you have a client backend hosted at localhost:3000 to pass into the Vocode React SDK. You'll likely need to tunnel port 3000 to ngrok / host your server in order to use it in the React SDK.

## Non-docker setup

`main.py` is just a simple python script, so you can run it with:

```
python main.py
```
