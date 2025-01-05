FROM python:{{python-version}}-slim

RUN useradd --create-home --shell /bin/bash workflow

WORKDIR /home/workflow

RUN apt-get -y update  \
    && apt-get install -y sqlite3 \
    && apt-get clean

COPY . .

RUN pip install --no-cache-dir -U ddeutil-workflow[app]

USER workflow

ENTRYPOINT ["ddeutil-workflow", "--help"]
