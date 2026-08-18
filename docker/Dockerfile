FROM python:3.12-slim AS base
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

FROM base AS dev
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
COPY src ./src
COPY examples ./examples
COPY tests ./tests
RUN pip install --no-cache-dir -e ".[dev]"
CMD ["mcp-evals", "health"]

FROM base AS runtime
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .
ENTRYPOINT ["mcp-evals"]
