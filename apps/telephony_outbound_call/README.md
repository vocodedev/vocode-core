# Telephonic Outbound Call

This repository contains the code for making outbound calls using telephony services.

## Prerequisites

Before running the code, make sure you have the following:

- [Telephony service account](https://www.twilio.com/en-us) - Sign up for a telephony service account and obtain the necessary credentials.
- [Python](https://www.python.org/downloads/) - Install Python on your machine.
- [Poetry](https://python-poetry.org/docs/#installation) - Install Poetry on your machine.
- [ngrok](https://ngrok.com/download) - Install ngrok on your machine.
- [OpenAI API key](https://beta.openai.com/) - Sign up for an OpenAI account and obtain the API key.
- [Deepgram API key](https://www.deepgram.com/) - Sign up for a Deepgram account and obtain the API key.
- [Together API key](https://together.ai/) - Sign up for a Together account and obtain the API key.
- [Azure Speech key](https://azure.microsoft.com/en-us/services/cognitive-services/speech-to-text/) - Sign up for an Azure Speech account and obtain the API key.


## Installation

1. Clone the repository:

    ```bash
    git clone https://github.com/your-username/telephony-outbound-call.git
    ```

2. Install the required dependencies via Poetry:

    ```bash
    poetry env use python3.11
    poetry install
    ```

## Configuration

1. Copy `.env.example` into `.env` file and update the following variables with your telephony service credentials:

    ```python
    ENV=

    PORT=

    TWILIO_ACCOUNT_SID=
    TWILIO_AUTH_TOKEN=

    ELEVEN_LABS_API_KEY=
    ELEVEN_LABS_MODEL=
    ELEVEN_LABS_VOICE=
    LLM_MODEL=
    GOOGLE_APPLICATION_CREDENTIALS=

    TWILIO_TO_NUMBER=
    TWILIO_FROM_NUMBER=
    TWILIO_WEBHOOK_URL=

    OPENAI_API_KEY=

    DEEPGRAM_API_KEY=

    TOGETHER_API_KEY=

    AZURE_SPEECH_KEY=
    AZURE_SPEECH_REGION=

    BASE_URL=

    ```

2. Save the changes.

## Usage

To start the server, run the following command:

```bash
poetry run uvicorn main:app --port=8000
```
To make an outbound call, run the following command:
```bash
poetry run python outbound_call.py
```
