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
- [Redis](https://redis.io/download) - Download and install Redis on your machine.
- [PortAudio](http://www.portaudio.com/download.html) - 
PortAudio is a cross-platform audio I/O library. Follow these steps to install PortAudio:
For linux
Run the following command to install PortAudio using the package manager:
```
sudo apt-get install portaudio19-dev
```
For macOS
Run the following command to install PortAudio using Homebrew:
```
brew install portaudio
```
For Windows
1. Download the PortAudio binaries from the [PortAudio website](http://www.portaudio.com/download.html).
2. Extract the downloaded ZIP file.
3. Copy the `portaudio_x86.dll` or `portaudio_x64.dll` file (depending on your system architecture) to your system's `System32` folder (typically located at `C:\Windows\System32`).

- [ffmpeg](https://ffmpeg.org/documentation.html) 
For linux
```
sudo apt install ffmpeg
```
For macos
```
brew install ffmpeg
```

For Windows
```
Download the FFmpeg binaries from the FFmpeg website and add the extracted directory containing the FFmpeg executables to your system's PATH environment variable.
```

- spacy model en_core_web_sm
```
poetry run python -m spacy download en_core_web_sm
```
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
poetry run uvicorn main:app --host=0.0.0.0 --port=3000
```
To make an outbound call, run the following command:
```bash
poetry run python outbound_call.py
```
