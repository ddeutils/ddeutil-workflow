FROM python:3.12-slim AS builder

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-install-project

COPY . .

RUN uv sync --frozen

FROM python:3.12-slim

COPY --from=builder /app /app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0"]
