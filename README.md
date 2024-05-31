# 🤫 Vocode 0.0.112 Early Preview

👋 Hey there, Vocode Explorer!

Congratulations! You've stumbled upon the Vocode 0.0.112 Early Preview Repo! Whether we (the Vocode team) sent you this link or you found it through your own detective work, we want to celebrate your awesomeness in the Vocode community with this exclusive sneak peek of our latest work!

## 🎉 What's Next?

We'd love to invite you to our private channel on Discord! [(Join us here!)](https://discord.gg/MVQD5bmf49) This is your VIP pass to chat with Vocode team members, get help, ask questions, and maybe even contribute to the 0.0.112 release!

## 🚨 Need Access?

If you can see this but don't have access to the new channels, just reach out to Mac, Ajay, George, or any other Vocode team member. We'll make sure you get in!

## 🤐 Keep It Under Wraps

We’re super excited to share this with you, but we’d appreciate it if you could keep this on the down-low for now. While we know you might share this with close friends, please avoid posting it in public places. We're still polishing things up for the big public launch!

## 📝 Brief Changelog

### 🧱Vocode Core Abstractions Revamp

- Improved Abstractions to enable faster customization of:
    - Agents
    - Transcribers
    - Synthesizers
    - Telephony Providers

### 👥 Conversation Mechanics

- Better endpointing (agnostic of transcribers)
- Better interruption handling

### 🕵️ Agents

- ✨NEW✨ Anthropic-based Agent
    - Supports all Claude 3 Models
- OpenAI GPT-4o Support
- Azure OpenAI revamp

### 💪 Actions

- ✨NEW✨ External Actions
- Improved Call Transfer
- ✨NEW✨ Wait Actions (IVR Navigation)
- ✨NEW✨ Phrase triggers for actions (instead of function calls)

### 🗣️ Synthesizers

- ElevenLabs
    - ✨NEW✨ Websocket-based Client
    - Updated RESTful client
- ✨NEW✨ PlayHT Synthesizer “v2” with [PlayHT On-Prem](https://docs.play.ht/reference/on-prem) Support
- [Rime Mist](https://rimelabs.mintlify.app/api-reference/models) support

### ✍️ Transcribers

- ✨NEW✨ Deepgram [built-in endpointing](https://developers.deepgram.com/docs/endpointing)

### 📞 Telephony

- Twilio
    - Stronger interruption handling by [clearing audio queues](https://www.twilio.com/docs/voice/media-streams/websocket-messages#send-a-clear-message)
- Vonage
    - Koala Noise Suppression

### 🎉 Miscellaneous

- ✨NEW✨  Loguru for improved logging formatting
    - Some new utilities to make setting up loguru in your projects fast and easy 😉
- Sentry for Metric / Error Collection
- Clean handling of content filters in ChatGPT agents
- Redis Message Queue for tracking mid-call events across different instances
