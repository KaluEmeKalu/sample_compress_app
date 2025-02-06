FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    # Prevents Python from buffering stdout and stderr
    PYTHONFAULTHANDLER=1 \
    # Keeps Python from generating .pyc files
    PYTHONDONTWRITEBYTECODE=1 \
    # Turns off buffering for easier container logging
    PYTHONUNBUFFERED=1 \
    # poetry configuration
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Create necessary directories
RUN mkdir -p /app/staticfiles /app/media /app/static

# Collect static files
RUN python manage.py collectstatic --noinput

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser
RUN chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8080

# Use a script to calculate workers based on CPU cores
COPY <<EOF /app/entrypoint.sh
#!/bin/sh
# Calculate number of workers based on CPU cores
WORKERS=$((2 * $(nproc) + 1))

# Start Gunicorn with optimal settings
exec gunicorn summit_project.wsgi:application \
    --bind 0.0.0.0:8080 \
    --workers $WORKERS \
    --threads 4 \
    --worker-class gthread \
    --worker-tmp-dir /dev/shm \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --timeout 120 \
    --keep-alive 5 \
    --log-level info \
    --access-logfile - \
    --error-logfile - \
    --capture-output \
    --enable-stdio-inheritance
EOF

RUN chmod +x /app/entrypoint.sh

# Run the application
CMD ["/app/entrypoint.sh"]