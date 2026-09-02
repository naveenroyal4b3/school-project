# Smart-Student Management System - application image.
FROM python:3.13-slim

# Unbuffered so container logs appear immediately; no .pyc files to stale out
# when the source is bind-mounted during development.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# netcat is used by the entrypoint to wait for MySQL to accept connections.
RUN apt-get update \
    && apt-get install -y --no-install-recommends netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Requirements are copied first so image layers cache: editing application code
# does not force a full dependency reinstall.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
