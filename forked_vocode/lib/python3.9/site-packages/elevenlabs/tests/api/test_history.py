import warnings


def test_history():
    from elevenlabs import History, HistoryItem

    page_size = 5
    # Test that we can get history
    history = History.from_api(page_size=page_size)
    assert isinstance(history, History)

    # Test that we can iterate over multiple pages lazily
    it = iter(history)
    for i in range(page_size * 3):
        try:
            assert isinstance(next(it), HistoryItem)
        except StopIteration:
            warnings.warn("Warning: not enough history items to test multiple pages.")
            break


def test_history_item_delete():
    import time
    from random import randint

    from elevenlabs import History, generate

    # Random text
    text = f"Test {randint(0, 1000)}"
    generate(text=text)  # Generate a history item to delete
    time.sleep(1)
    history = History.from_api(page_size=1)
    history_item = history[0]
    # Check that item matches
    assert history_item.text == text
    history_item.delete()
    # Test that the history item was deleted
    history = History.from_api(page_size=1)
    assert len(history) == 0 or history[0].text != text
