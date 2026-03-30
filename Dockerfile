# Dockerfile
# ──────────────────────────────────────────────────────────────
# FastAPI backend — replaces old Streamlit setup
# ──────────────────────────────────────────────────────────────

FROM python:3.10-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy source code
COPY . .

# Create snapshots directory
RUN mkdir -p snapshots

# Expose FastAPI port
EXPOSE 8000

# Run FastAPI with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]