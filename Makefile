.PHONY: lint lint_diff

chat:
	poetry run python playground/streaming/agent/chat.py

speak:
	poetry run python playground/streaming/transcriber/speak.py

listen:
	poetry run python playground/streaming/synthesizer/listen.py

PYTHON_FILES=.
lint: PYTHON_FILES=.
lint_diff: PYTHON_FILES=$(shell git diff --name-only --diff-filter=d main | grep -E '\.py$$')

lint lint_diff:
	poetry run black $(PYTHON_FILES)

