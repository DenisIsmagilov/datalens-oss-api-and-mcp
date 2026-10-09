FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY formula-docs ./formula-docs
COPY scripts ./scripts
COPY packs /packs
RUN mkdir -p /data
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${NEURO_PORT:-8396}"]
