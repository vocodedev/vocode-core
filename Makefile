.PHONY: chat speak listen lint lint_diff help

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

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "Targets:"
	@echo "  chat        Run chat agent"
	@echo "  speak       Speak text"
	@echo "  listen      Listen to audio"
	@echo "  lint        Lint all Python files"
	@echo "  lint_diff   Lint changed Python files"
	@echo "  help        Show this help message"

