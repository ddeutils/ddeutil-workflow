FROM python:3.9.13-slim

RUN useradd --create-home --shell /bin/bash worker

WORKDIR /home/worker

RUN apt-get -y update  \
    && apt-get install -y sqlite3 \
    && apt-get clean

COPY . .

RUN pip install --no-cache-dir -U ddeutil-workflow[all]

USER worker

ENTRYPOINT ["workflow-cli"]
