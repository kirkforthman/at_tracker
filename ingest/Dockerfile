# Ingest worker. Base image pinned by tag + digest (docs/adr/0003).
FROM python:3.14.4-slim@sha256:2ca02f32b4d9d893863367ce07ec1972819f476dd38d8612f2a9cb6a41cbb727
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Run from source (not an installed package) so migrations/ and the replay fixture resolve.
COPY at_ingest/ at_ingest/
COPY migrations/ migrations/
COPY tests/fixtures/opensky/synthetic_sequence.json tests/fixtures/opensky/
RUN useradd --system --uid 10001 app
USER app
CMD ["python", "-m", "at_ingest.worker"]
