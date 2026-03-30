# Dockerfile
# ──────────────────────────────────────────────────────────────
# FastAPI backend — replaces old Streamlit setup
# ──────────────────────────────────────────────────────────────

FROM python:3.10-slim

# Fix for rootless Podman UID/GID namespace issues
RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -m appuser

WORKDIR /app

ENV PYTHONUNBUFFERED=1

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy source code
COPY . .

# Create snapshots directory and fix ownership
RUN mkdir -p snapshots && \
    chown -R 1000:1000 /app

# Switch to non-root user
USER 1000

# Expose FastAPI port
EXPOSE 8000

# Run FastAPI with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]