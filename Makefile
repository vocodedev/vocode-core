.PHONY: deploy build-dev run-dev lint lint_diff typecheck typecheck_diff test help

deploy:
	docker buildx build --platform=linux/amd64 -t speaksage-vocode-python .
	docker tag speaksage-vocode-backend:latest cstigler/speaksage-vocode-backend:latest
	docker push cstigler/speaksage-vocode-backend:latest

build-dev:
	source ./dev-env/bin/activate
	docker build -t speaksage-vocode-backend .

run-dev:
	docker build -t speaksage-vocode-backend . && docker run --env-file=./apps/client_backend/.env -p 8080:8080 -t speaksage-vocode-backend

PYTHON_FILES=.
lint: PYTHON_FILES=vocode/ apps/
lint_diff typecheck_diff: PYTHON_FILES=$(shell git diff --name-only --diff-filter=d main | grep -E '\.py$$')

lint lint_diff:
	poetry run black $(PYTHON_FILES)

typecheck:
	poetry run mypy -p vocode
	poetry run mypy -p apps

typecheck_diff:
	poetry run mypy $(PYTHON_FILES)

test:
	poetry run pytest

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "Targets:"
	@echo "  deploy      Build, tag and push Docker image"
	@echo "  build-dev   Build Docker image for development"
	@echo "  run-dev     Build and run Docker image for development"
	@echo "  lint        Lint all Python files"
	@echo "  lint_diff   Lint changed Python files"
	@echo "  typecheck   Run mypy type checking"
	@echo "  typecheck_diff Run mypy type checking on changed files"
	@echo "  test        Run tests"
	@echo "  help        Show this help message"
