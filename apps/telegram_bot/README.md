# Telegram Bot

## Docker

1. Set up the configuration for your telegram bot in `main.py`.
2. Set up an .env file using the template
3. Create a Telegram Bot token and link using The Bot Father: https://t.me/botfather

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

Now you have a telegram bot running. Visit the link you chose during the Telegram bot creation process
.
## Non-docker setup

`main.py` is just a simple python script, so you can run it with:

```
poetry install
poetry run python main.py
```
