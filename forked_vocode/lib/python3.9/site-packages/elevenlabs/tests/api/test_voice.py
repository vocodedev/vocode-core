from ..utils import use_play


def test_voice_from_id():
    from elevenlabs import Voice, VoiceSettings

    # Test that we can get a voice from id
    voice_id = "21m00Tcm4TlvDq8ikWAM"
    voice = Voice.from_id(voice_id)
    assert isinstance(voice, Voice)

    assert voice.voice_id == voice_id
    assert voice.name == "Rachel"
    assert voice.category == "premade"
    assert isinstance(voice.settings, VoiceSettings)


def test_voice_clone():
    from elevenlabs import Voice, clone, generate, play

    from ..utils import as_local_files

    voice_file_urls = [
        "https://user-images.githubusercontent.com/12028621/235474694-584f7103-dab2-4c39-bb9a-8e5f00be85da.webm",
        "https://user-images.githubusercontent.com/12028621/235474694-584f7103-dab2-4c39-bb9a-8e5f00be85da.webm",
    ]

    with as_local_files(voice_file_urls) as files:
        voice = clone(
            name="Alex",
            description=(
                "An old American male voice with a slight hoarseness in his throat."
                " Perfect for news"
            ),
            files=files,
        )

    assert isinstance(voice, Voice)
    assert voice.voice_id is not None
    assert voice.name == "Alex"
    assert voice.category == "cloned"
    assert len(voice.samples) == len(voice_file_urls)

    audio = generate(
        text="Voice clone test successful.",
        voice=voice,
    )
    assert isinstance(audio, bytes) and len(audio) > 0
    voice.delete()

    if use_play:
        play(audio)


def test_voice_design():
    from elevenlabs import Accent, Age, Gender, Voice, VoiceDesign, generate, play

    voice_design = VoiceDesign(
        name="Lexa",
        text=(
            "Hi! My name is Lexa, I'm a voice design test. I should have a middle aged"
            " female voice with a british accent. "
        ),
        gender=Gender.female,
        age=Age.middle_aged,
        accent=Accent.british,
        accent_strength=1.5,
    )

    audio = voice_design.generate()
    assert isinstance(audio, bytes) and len(audio) > 0
    if use_play:
        play(audio)

    voice = Voice.from_design(voice_design)
    assert isinstance(voice, Voice)

    audio = generate(
        text="Voice design test successful.",
        voice=voice,
    )
    assert isinstance(audio, bytes) and len(audio) > 0
    voice.delete()
    if use_play:
        play(audio)


def test_voices():
    from elevenlabs import Voice, Voices

    # Test that we can get voices from api
    voices = Voices.from_api()

    assert isinstance(voices, Voices)
    assert len(voices) > 0
    assert isinstance(voices[0], Voice)

    for voice in voices:
        assert isinstance(voice, Voice)
