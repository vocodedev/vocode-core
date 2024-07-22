FROM vocodedev/vocode:latest

WORKDIR /code
COPY ./pyproject.toml /code/pyproject.toml
COPY ./poetry.lock /code/poetry.lock
RUN pip install --no-cache-dir --upgrade poetry
RUN poetry config virtualenvs.create false
RUN poetry install --no-dev --no-interaction --no-ansi
RUN pip install twilio
COPY main.py /code/main.py
COPY speller_agent.py /code/speller_agent.py
COPY sms_send_appointment_noti.py /code/sms_send_appointment_noti.py
COPY custom_action_factory.py /code/custom_action_factory.py
COPY custom_agent_factory.py /code/custom_agent_factory.py
COPY custom_agent.py /code/custom_agent.py

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3000"]
