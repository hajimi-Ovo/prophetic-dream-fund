# ============================================================
# Stage 1 — Builder: compile Python dependencies
# ============================================================
FROM python:3.11-slim AS builder

# Install build-time system dependencies (needed to compile asyncpg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create and activate a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python production dependencies into the venv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ============================================================
# Stage 2 — Runner: minimal production image
# ============================================================
FROM python:3.11-slim

# Install only the runtime shared library (not the dev headers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /code

# Copy application source
COPY app/ /code/app/

# Make the app package importable
ENV PYTHONPATH=/code

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
