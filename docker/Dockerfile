# VPS Automation Server Dockerfile - Production-ready container

# Use Python 3.11 slim as base image
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Browser dependencies
    wget \
    gnupg \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    # System utilities
    curl \
    git \
    # Build dependencies
    build-essential \
    # Process monitoring
    htop \
    procps \
    # Network utilities
    iputils-ping \
    net-tools \
    # Browser dependencies for Playwright
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libdrm2 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libxss1 \
    libasound2 \
    libatspi2.0-0 \
    libgtk-3-0 \
    libxshmfence1 \
    # Virtual display for headless browser
    xvfb \
    # Cleanup
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (for Playwright browser installation)
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs

# Create app user and directory
RUN useradd --create-home --shell /bin/bash app \
    && mkdir -p /app \
    && chown -R app:app /app

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY docker/requirements.txt /app/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ /app/app/
COPY requirements.txt /app/

# Install additional Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers as app user
USER app
RUN python -m playwright install-deps || true
RUN python -m playwright install chromium firefox webkit

# Switch back to root for final setup
USER root

# Create necessary directories
RUN mkdir -p /app/logs /app/tmp \
    && chown -R app:app /app

# Set up virtual display for headless browsers
ENV DISPLAY=:99

# Create startup script
RUN echo '#!/bin/bash\n\
# Clean up any existing X locks\n\
rm -f /tmp/.X99-lock\n\
# Start virtual display\n\
Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset &\n\
# Wait for display to be ready\n\
sleep 3\n\
# Start the application\n\
exec "$@"' > /app/entrypoint.sh \
    && chmod +x /app/entrypoint.sh \
    && chown app:app /app/entrypoint.sh

# Switch to app user
USER app

# Expose ports
EXPOSE 8000 9090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Multi-stage build for production
FROM base as production

# Copy only necessary files for production
COPY --from=base /app /app
COPY --from=base /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=base /usr/local/bin /usr/local/bin

# Production environment
ENV ENVIRONMENT=production
ENV DEBUG=false
ENV LOG_LEVEL=INFO

# Final production image
FROM production as final

USER app
WORKDIR /app

# Final command for production
CMD ["gunicorn", "app.main:app", "-w", "2", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--timeout", "300"] 