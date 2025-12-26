FROM python:3.11-slim

LABEL org.opencontainers.image.description Trivial ParishSoft PDF letter processor

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY templates/ templates/

# Create directories for uploads and logs
RUN mkdir -p /tmp/pdf-processor/uploads /tmp/pdf-processor/processing /var/log/pdf-processor

# Expose port
EXPOSE 5000

# Set environment variables
ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1

# Run with gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "300", "--access-logfile", "/var/log/pdf-processor/access.log", "--error-logfile", "/var/log/pdf-processor/error.log", "app:app"]
