# Build

Note for building the Docker image.

## Docker Image

```shell
docker build -t ddeutil-workflow:latest -f ./.container/Dockerfile .
```

## Docker Container

```shell
docker run --name ddeutil-worker -t --rm ddeutil-workflow:latest version
```
