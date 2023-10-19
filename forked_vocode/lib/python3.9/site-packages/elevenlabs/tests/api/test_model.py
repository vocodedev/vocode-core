def test_model():
    from elevenlabs import Model, Models

    # Test that we can get all models
    models = Models.from_api()
    assert isinstance(models, Models)
    assert len(models) > 0
    assert isinstance(models[0], Model)
