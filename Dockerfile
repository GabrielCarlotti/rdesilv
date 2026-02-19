# Dockerfile à placer à la racine du repo rdesilv (backend)
FROM python:3.12-slim

# Installer uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copier les fichiers de dépendances en premier (cache Docker)
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev

# Copier le reste du code
COPY . .

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uv", "run", "prod"]
