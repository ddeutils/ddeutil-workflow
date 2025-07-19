FROM python:3.9.13-slim

RUN useradd --create-home --shell /bin/bash worker

WORKDIR /home/worker

RUN apt-get -y update  \
    && apt-get install -y sqlite3 curl \
    && apt-get clean

COPY --from=ghcr.io/astral-sh/uv:0.8.0 /uv /uvx /bin/

ENV UV_SYSTEM_PYTHON=1

COPY . .

RUN uv pip install -e ".[all]" --no-cache-dir

EXPOSE 8888

USER worker

ENTRYPOINT ["workflow-cli"]

CMD ["api"]
