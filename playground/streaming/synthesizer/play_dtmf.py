import asyncio
from vocode.streaming.synthesizer.base_synthesizer import dtmf_wav_path
from vocode.streaming.models.audio_encoding import AudioEncoding
from vocode.streaming.utils import convert_wav
from vocode.streaming.output_device.speaker_output import SpeakerOutput

async def play_dtmf(key: str):
  speaker_output = SpeakerOutput.from_default_device()

  wav_file_path = dtmf_wav_path(key)

  print(wav_file_path)

  output_bytes = convert_wav(
      wav_file_path,
      output_sample_rate=48000,
      output_encoding=AudioEncoding.LINEAR16,
  )

  await speaker_output.send_async(output_bytes)

async def main():
  await play_dtmf("0")
  await play_dtmf("1")
  await play_dtmf("2")
  await play_dtmf("3")
  await play_dtmf("4")
  await play_dtmf("5")
  await play_dtmf("6")
  await play_dtmf("7")
  await play_dtmf("8")
  await play_dtmf("9")

asyncio.run(main())
