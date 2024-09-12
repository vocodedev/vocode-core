from loguru import logger


def ensure_punkt_installed():
    try:
        from nltk.data import find

        find("tokenizers/punkt_tab")
    except LookupError:
        from nltk import download

        # If not installed, download 'punkt_tab'
        logger.info("Downloading 'punkt_tab' tokenizer...")
        download("punkt_tab")
        logger.info("'punkt_tab' tokenizer downloaded successfully.")
