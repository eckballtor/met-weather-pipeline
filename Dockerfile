# Full pipeline in one image: the build runs ingestion + dbt, so the
# served warehouse is data-as-of-image-build.
FROM python:3.12-slim

# Official uv binary from Astral's image.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Dependencies first (this layer stays cached until pyproject/lock change).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Project code.
COPY profiles.yml dbt_project.yml ./
COPY data/ data/
COPY ingest/ ingest/
COPY models/ models/
COPY tests/ tests/
COPY api/ api/

# Bake the warehouse at build time — the image build IS a pipeline run.
RUN uv run python -m ingest.ingest && uv run dbt build --profiles-dir .

ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uv run uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]
