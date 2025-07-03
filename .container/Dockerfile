FROM python:3.9.13-slim

RUN useradd --create-home --shell /bin/bash worker

WORKDIR /home/worker

RUN apt-get -y update  \
    && apt-get install -y sqlite3 curl \
    && apt-get clean

COPY --from=ghcr.io/astral-sh/uv:0.6.14 /uv /uvx /bin/

COPY . .

RUN uv pip install --no-cache-dir -U ddeutil-workflow[all]

EXPOSE 8888

USER worker

ENTRYPOINT ["workflow-cli"]

CMD ["api"]
