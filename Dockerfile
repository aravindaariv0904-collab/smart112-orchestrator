# ==============================================================================
# SMART 112: Production Zero-Cost Deployment Dockerfile (Hugging Face Spaces & Cloud)
# Stage 1: Build React Vite TypeScript Frontend Assets
# Stage 2: Python 3.11 FastAPI Orchestration Runtime with Embedded Static UI
# ==============================================================================

# ----------------- Stage 1: Frontend Build -----------------
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend

# Install dependencies with caching
COPY frontend/package*.json ./
RUN npm ci || npm install

# Copy frontend source and compile static production bundle
COPY frontend/ ./
RUN npm run build

# ----------------- Stage 2: Production Backend Runtime -----------------
FROM python:3.11-slim

LABEL maintainer="SMART 112 Public Safety Core Engineering"
LABEL description="AI-Augmented Emergency Dispatch Orchestrator for Hugging Face Spaces"

# Install essential system packages for faster-whisper (ffmpeg) and audio decoding
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Hugging Face Spaces mandates non-root UID 1000 user execution
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Install backend dependencies
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r backend/requirements.txt

# Copy application layers with appuser ownership
COPY --chown=appuser:appuser backend/ ./backend/
COPY --chown=appuser:appuser ai/ ./ai/
COPY --chown=appuser:appuser multimodal/ ./multimodal/
COPY --chown=appuser:appuser contracts/ ./contracts/
COPY --chown=appuser:appuser scripts/ ./scripts/
COPY --chown=appuser:appuser alembic.ini ./

# Copy compiled static frontend distribution from Stage 1
COPY --from=frontend-builder --chown=appuser:appuser /app/frontend/dist ./frontend/dist

# Switch to non-root user
USER appuser

# Environment parameters
ENV PYTHONPATH=/app
ENV PORT=7860
ENV WHISPER_DEVICE=cpu
ENV FORCE_SQLITE=false

# Expose standard Hugging Face Spaces port
EXPOSE 7860

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

# Launch production Uvicorn ASGI server serving both API and static frontend
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "7860"]

