from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)

from vocode.turn_based.transcriber.whisper_transcriber import WhisperTranscriber
from vocode.turn_based.agent.chat_gpt_agent import ChatGPTAgent
from vocode.turn_based.synthesizer.coqui_synthesizer import CoquiSynthesizer

# Optional alternative synthesizers:
from vocode.turn_based.synthesizer.stream_elements_synthesizer import (
    StreamElementsSynthesizer,
)
from vocode.turn_based.synthesizer.eleven_labs_synthesizer import ElevenLabsSynthesizer
from vocode.turn_based.synthesizer.play_ht_synthesizer import PlayHtSynthesizer
from vocode.turn_based.synthesizer.azure_synthesizer import AzureSynthesizer
from vocode.turn_based.synthesizer.coqui_tts_synthesizer import CoquiTTSSynthesizer
from vocode.turn_based.synthesizer.rime_synthesizer import RimeSynthesizer

from pydub import AudioSegment
import io
import logging
import os
import subprocess
import inspect
from typing import Tuple, Union
import pickle

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# Synthesizer class must be one of the following (do not change without adding support):
supported_classes = [
    CoquiSynthesizer,
    StreamElementsSynthesizer,
    ElevenLabsSynthesizer,
    PlayHtSynthesizer,
    AzureSynthesizer,
    CoquiTTSSynthesizer,
    RimeSynthesizer,
]
""" CONFIGURATION START """
# Required environment variables containing API key: OPENAI_API_KEY, TELEGRAM_BOT_KEY, and your Vocode synthesizers classes corresponding API key variable

# Your chosen synthesizer provider's corresponding Vocode turn_based class instance
SYNTH = CoquiSynthesizer(xtts=True)

# Array of tuples (synthesizer's voice id, nickname, description if text to voice)
DEFAULT_VOICES = [("d2bd7ccb-1b65-4005-9578-32c4e02d8ddf", "Coqui Default", None)]

# instructions to the language model responsible for generating response transcript.
SYSTEM_PROMPT = "You are having a voice-to-voice conversation with a user. Always pretend you are a real human. Do not avoid or decline to answer questions because you are not human."
""" CONFIGURATION END """

# key=synth class, value=attribute that chooses the provider voice
voice_attr_of = {
    ElevenLabsSynthesizer: "voice_id",
    PlayHtSynthesizer: "voice",
    StreamElementsSynthesizer: "voice",
    AzureSynthesizer: "voice_name",
    CoquiSynthesizer: "voice_id",
    CoquiTTSSynthesizer: "speaker",
    RimeSynthesizer: "speaker",
}
assert set(voice_attr_of.keys()) == set(
    supported_classes
), "supported_classes must match the keys of voice_attr_of!"

assert (
    type(SYNTH) in voice_attr_of.keys()
), "Synthesizer class must be one of the supported ones!"
# check voice_attr_of is correct by asserting all classes have their corresponding value as a parameter in the init function
for key, value in voice_attr_of.items():
    assert value in inspect.signature(key.__init__).parameters


class InMemoryDB:
    def __init__(self):
        # Initialize an empty dictionary to store user data
        self.db = {}

    def __getitem__(self, chat_id):
        # Return the user data for a given user id, or create a new one if not found
        if chat_id not in self.db:
            self.db[chat_id] = {
                "voices": DEFAULT_VOICES,
                "current_voice": DEFAULT_VOICES[0],
                "current_conversation": None,
            }
        return self.db[chat_id]

    def __setitem__(self, chat_id, user_data):
        # Set the user data for a given user id
        self.db[chat_id] = user_data


class VocodeBotResponder:
    def __init__(self, transcriber, system_prompt, synthesizer, db=None):
        self.transcriber = transcriber
        self.system_prompt = system_prompt
        self.synthesizer = synthesizer
        self.db = db if db else InMemoryDB()
        self.chat_ids = []

    def get_agent(self, chat_id):
        # Get current voice name and description from DB
        _, voice_name, voice_description = self.db[chat_id].get(
            "current_voice", (None, None, None)
        )

        # Augment prompt based on available info
        prompt = self.system_prompt
        if voice_description != None:
            prompt += " Pretend to be {0}. This is a demo of Coqui TTS's voice creation tool, so your responses are fun, always in character, and relevant to that voice description.".format(voice_description)
        if voice_name != None:
            prompt += (
                " Pretend to be {0}. Act like {0} and identify yourself as {0}.".format(voice_name)
            )
        print("System prompt: ", prompt)

        # Load saved conversation if it exists
        convo_string = self.db[chat_id]["current_conversation"]
        agent = ChatGPTAgent(
            system_prompt=prompt,
            memory=pickle.loads(convo_string) if convo_string else None
        )

        return agent

    # input can be audio segment or text
    async def get_response(
        self, chat_id, input: Union[str, AudioSegment]
    ) -> Tuple[str, AudioSegment]:
        # If input is audio, transcribe it
        if isinstance(input, AudioSegment):
            input = self.transcriber.transcribe(input)

        # Get agent response
        agent = self.get_agent(chat_id)
        agent_response = agent.respond(input)

        # Set current synthesizer voice from db
        voice_id, _, voice_description = self.db[chat_id].get(
            "current_voice", (None, None, None)
        )

        # If we have a Coqui voice prompt, use that. Otherwise, set ID as synthesizer expects.
        if voice_description is not None:
            self.synthesizer.voice_prompt = voice_description
        else:
            setattr(self.synthesizer, voice_attr_of[type(self.synthesizer)], voice_id)

        # Synthesize response
        synth_response = await self.synthesizer.async_synthesize(agent_response)

        # Save conversation to DB
        self.db[chat_id]["current_conversation"] = pickle.dumps(agent.memory)

        return agent_response, synth_response

    async def handle_telegram_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        chat_id = update.effective_chat.id
        # Create user entry in DB
        self.db[chat_id] = {
            "voices": DEFAULT_VOICES,
            "current_voice": DEFAULT_VOICES[0],
            "current_conversation": None,
        }
        start_text = """
I'm a voice chatbot, send a voice message to me and I'll send one back!" Use /help to see available commands.
"""
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=start_text
        )

    async def handle_telegram_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        chat_id = update.effective_chat.id
        # Accept text or voice messages
        if update.message.voice:
            user_telegram_voice = await context.bot.get_file(
                update.message.voice.file_id
            )
            bytes = await user_telegram_voice.download_as_bytearray()
            input = AudioSegment.from_file(
                io.BytesIO(bytes), format="ogg", codec="libopus"
            )
        elif update.message.text:
            input = update.message.text
        else:
            # No audio or text, complain to user.
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="""
Sorry, I only respond to commands, voice, or text messages. Use /help for more information.""",
            )
            return

        # Get audio response from LLM/synth and reply
        agent_response, synth_response = await self.get_response(chat_id, input)
        out_voice = io.BytesIO()
        synth_response.export(out_f=out_voice, format="ogg", codec="libopus")
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=agent_response
        )
        await context.bot.send_voice(chat_id=chat_id, voice=out_voice)

    async def handle_telegram_select_voice(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        chat_id = update.effective_chat.id
        if not (context.args):
            await context.bot.send_message(
                chat_id=chat_id,
                text="You must include a voice id. Use /list to list available voices",
            )
            return
        new_voice_id = context.args[0]

        user_voices = self.db[chat_id]["voices"]
        if len(user_voices) <= new_voice_id:
            await context.bot.send_message(
                chat_id=chat_id,
                text="Sorry, I do not recognize that voice. Use /list to list available voices.",
            )
            return
        else:
            self.db[chat_id]["current_voice"] = user_voices[new_voice_id]
            # Reset conversation
            self.db[chat_id]["current_conversation"] = None
            await context.bot.send_message(
                chat_id=chat_id, text="Voice changed successfully!"
            )

    async def handle_telegram_create_voice(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        chat_id = update.effective_chat.id
        if type(self.synthesizer) is not CoquiSynthesizer:
            await context.bot.send_message(
                chat_id=chat_id,
                text="Sorry, voice creation is only supported for Coqui TTS.",
            )
            return
        if not (context.args):
            await context.bot.send_message(
                chat_id=chat_id,
                text="You must include a voice description.",
            )
            return

        voice_description = " ".join(context.args)

        # Coqui voices are created at synthesis-time, so don't have an ID nor name.
        new_voice = (None, None, voice_description)
        self.db[chat_id]["voices"].append(new_voice)
        self.db[chat_id]["current_voice"] = new_voice
        # Reset conversation
        self.db[chat_id]["current_conversation"] = None

        await context.bot.send_message(
            chat_id=chat_id, text="Voice changed successfully!"
        )

    async def handle_telegram_list_voices(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        chat_id = update.effective_chat.id
        user_voices = self.db[chat_id]["voices"]  # array (id, name, description)
        # Make string table of id, name, description
        voices = "\n".join(
            [
                f"{id}: {name if name else ''}{f' - {description}' if description else ''}"
                for id, (internal_id, name, description) in enumerate(user_voices)
            ]
        )
        await context.bot.send_message(
            chat_id=chat_id, text=f"Available voices:\n{voices}"
        )

    async def handle_telegram_who(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        chat_id = update.effective_chat.id
        _, name, description = _, voice_name, voice_description = self.db[chat_id].get(
            "current_voice", (None, None, None)
        )
        current = name if name else description
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"I am currently '{current}'.",
        )

    async def handle_telegram_help(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        help_text = """
I'm a voice chatbot, here to talk with you! Here's what you can do:

- Send me a voice message and I'll respond with a voice message.
- Use /list to see a list of available voices.
- Use /voice <voice_id> to change the voice I use to respond and reset the conversation.
- Use /who to see what voice I currently am.
- Use /help to see this help message again.
"""
        if type(self.synthesizer) is CoquiSynthesizer:
            help_text += "\n- Use /create <voice_description> to create a new Coqui TTS voice from a text prompt and switch to it."
        await context.bot.send_message(chat_id=update.effective_chat.id, text=help_text)

    async def handle_telegram_unknown_cmd(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="""
Sorry, I didn\'t understand that command. Use /help to see available commands""",
        )


if __name__ == "__main__":
    transcriber = WhisperTranscriber()
    voco = VocodeBotResponder(transcriber, SYSTEM_PROMPT, SYNTH)
    application = ApplicationBuilder().token(os.environ["TELEGRAM_BOT_KEY"]).build()
    application.add_handler(CommandHandler("start", voco.handle_telegram_start))
    application.add_handler(
        MessageHandler(~filters.COMMAND, voco.handle_telegram_message)
    )
    application.add_handler(CommandHandler("create", voco.handle_telegram_create_voice))
    application.add_handler(CommandHandler("voice", voco.handle_telegram_select_voice))
    application.add_handler(CommandHandler("list", voco.handle_telegram_list_voices))
    application.add_handler(CommandHandler("who", voco.handle_telegram_who))
    application.add_handler(CommandHandler("help", voco.handle_telegram_help))
    application.add_handler(
        MessageHandler(filters.COMMAND, voco.handle_telegram_unknown_cmd)
    )
    application.run_polling()
