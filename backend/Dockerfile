# --- builder ---
FROM python:3.12-slim AS builder
WORKDIR /code
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- runtime ---
FROM python:3.12-slim
RUN useradd -u 1000 -m appuser
WORKDIR /code
COPY --from=builder /install /usr/local
COPY app ./app
COPY shared ./shared
COPY alembic ./alembic
COPY alembic.ini .
ENV PYTHONUNBUFFERED=1
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]