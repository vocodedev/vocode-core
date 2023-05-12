# This script is used to generate wav files for DTMF tones.
# 
# Using this approach: https://www.cloudacm.com/?p=3147
# 
# Before running this, make sure you have the `sox` tool installed:
#  `brew install sox`
# Then simply run this:
# `python vocode/streaming/synthesizer/dtmf_audio/generate_wav_files.py`
# 
# For reference, here are alternative sources for DTMF tones:
# https://onlinetonegenerator.com/dtmf.html - more cumbersome to record
# https://freesound.org/people/ialexs/packs/10184/ - these sounded distorted through Twilio
# https://evolution.voxeo.com/library/audio/prompts/dtmf/index.jsp

import os
import time

duration = 0.5 # half second
duration_ms = int(duration * 1000)

key_info = '''
697 1209 - 1
697 1336 - 2
697 1477 - 3
697 1633 - A
770 1209 - 4
770 1336 - 5
770 1477 - 6
770 1633 - B
852 1209 - 7
852 1336 - 8
852 1477 - 9
852 1633 - C
941 1209 - *
941 1336 - 0
941 1477 - #
941 1633 - D
'''

keys = []
for line in key_info.split("\n"):
  if line:
    parts = line.split(" ")
    keys.append({
      "key": parts[-1],
      "freq1": parts[0],
      "freq2": parts[1],
    })

replacements = {
  "*": "star",
  "#": "pound",
}

for key in keys:
  key_name = key["key"]
  if key_name in replacements:
    key_name = replacements[key_name]
  filename = "dtmf-%s.%sms.wav" % (key_name, duration_ms)
  # Play the sound and record it
  command = "play -n synth %s sin %s sin %s remix - | rec %s trim 0 %s" % (duration, key["freq1"], key["freq2"], filename, duration)
  os.system(command)
  # Convert it to the format that the wave library expects
  new_filename = filename.replace(".wav", ".b16.wav")
  command = "sox %s -b 16 %s" % (filename, new_filename)
  os.system(command)
  # Delete the original file
  os.remove(filename)
  time.sleep(duration)
