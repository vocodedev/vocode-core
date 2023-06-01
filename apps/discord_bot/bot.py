import os
import io
import logging
import asyncio

import discord
from discord.sinks import Sink, Filters, default_filters, AudioData

from vocode.streaming.transcriber import DeepgramTranscriber
from vocode.streaming.models.audio_encoding import AudioEncoding
from vocode.streaming.models.transcriber import DeepgramTranscriberConfig
from pydub import AudioSegment

bot = discord.Bot(debug_guilds=[1113610683737722913])
connections = {}

logger = logging.getLogger(__name__)

transcriber = DeepgramTranscriber(DeepgramTranscriberConfig(sampling_rate=44100, audio_encoding=AudioEncoding.LINEAR16, chunk_size=2048))

import wave
f = wave.open("test.wav", "wb")
f.setnchannels(1)
f.setsampwidth(2)
f.setframerate(44100)
class VocodeSink(Sink):
    @Filters.container
    def write(self, data, user):
        if user not in self.audio_data:
            file = io.BytesIO()
            self.audio_data.update({user: AudioData(file)})

        file = self.audio_data[user]
        file.write(data)
        data = AudioSegment.from_raw(io.BytesIO(data), sample_width=2, frame_rate=48000, channels=2)
        # convert data audio segment to wav with 1 channel and frame rate 44100
        data = data.set_channels(1)
        data = data.set_frame_rate(44100)
        data = data.set_sample_width(2)
        raw = io.BytesIO()
        data.export(raw, format="raw")
        f.writeframes(raw.getvalue())
        raw.seek(0)
        transcriber.send_audio(raw)
        # write the data to a wave file
        
        # f.writeframes(data)

async def print_transcription_task():
    while True:
        print("getting")
        transcription = await transcriber.output_queue.get()
        print("got it!")
        print(transcription)



async def finished_callback(sink, channel: discord.TextChannel, *args):
    recorded_users = [f"<@{user_id}>" for user_id, audio in sink.audio_data.items()]
    await sink.vc.disconnect()
    files = [
        discord.File(audio.file, f"{user_id}.{sink.encoding}")
        for user_id, audio in sink.audio_data.items()
    ]
    await channel.send(
        f"Finished! Recorded audio for {', '.join(recorded_users)}.", files=files
    )

@bot.command()
async def start(ctx: discord.ApplicationContext):
    """Record your voice!"""
    transcriber.start()
    
    voice = ctx.author.voice

    if not voice:
        return await ctx.respond("You're not in a vc right now")

    vc = await voice.channel.connect()
    connections.update({ctx.guild.id: vc})

    vc.start_recording(
        VocodeSink(),
        finished_callback,
        ctx.channel,
    )
    asyncio.create_task(print_transcription_task())

    await ctx.respond("The recording has started!")


@bot.command()
async def stop(ctx: discord.ApplicationContext):
    """Stop recording."""
    if ctx.guild.id in connections:
        vc = connections[ctx.guild.id]
        vc.stop_recording()
        del connections[ctx.guild.id]
        await ctx.delete()
    else:
        await ctx.respond("Not recording in this guild.")

# async def main():
    # transcriber.start()
    # async def print_transcription_task():
    #     while True:
    #         transcription = await transcriber.output_queue.get()
    #         print(transcription)

    # asyncio.create_task(print_transcription_task())

bot.run(os.environ["DISCORD_BOT_TOKEN"])

# if __name__ == "__main__":
#     main()



# @client.tree.command()
# async def join(interaction: discord.Interaction):
#     """Joins the voice channel you are in."""
#     # get the name of the voice channel that the user is in
#     voice_channel = interaction.user.voice
#     if voice_channel is None:
#         await interaction.response.send_message('You are not in a voice channel.')
#     else:
#         channel = interaction.user.voice.channel
#         await interaction.response.send_message(f'You are in {channel.name}')
#         voice_client = await channel.connect()
#         source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio("test.wav"))
#         voice_client.play(source, after=lambda e: print(f'Player error: {e}') if e else None)
#         while voice_client.is_playing():
#             await asyncio.sleep(1)
#         await voice_client.disconnect()
