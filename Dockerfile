FROM python:3.14-slim

WORKDIR /app

COPY ./requirements.txt  /app/requirements.txt

RUN uv sync

COPY ./src /app/src

CMD ["uv", "run", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]