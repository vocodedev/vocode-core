FROM vocodedev/vocode:latest

WORKDIR /code
COPY ./pyproject.toml /code/pyproject.toml
COPY ./poetry.lock /code/poetry.lock
RUN pip install --no-cache-dir --upgrade poetry
RUN poetry config virtualenvs.create false
RUN poetry install --no-dev --no-interaction --no-ansi
COPY main.py /code/main.py
COPY speller_agent.py /code/speller_agent.py

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3000"]
