def test_user():
    from elevenlabs import Subscription, User

    # Test that we can get current user
    user = User.from_api()
    assert isinstance(user, User)
    assert isinstance(user.subscription, Subscription)
