# Dockerfile for Romanian Legislative API Client with Streamlit Interface
# Uses multi-stage build for smaller final image

# ===== BUILD STAGE =====
FROM python:3.9-slim AS builder

# Set environment variables for build
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install system dependencies required for Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --user --no-warn-script-location -r requirements.txt

# ===== RUNTIME STAGE =====
FROM python:3.9-slim AS runtime

# Set environment variables for runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TZ=Europe/Bucharest

# Install runtime system dependencies (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 \
    libxslt1.1 \
    tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --gid 1001 --home /home/appuser --no-create-home appuser

ENV HOME=/home/appuser
ENV PYTHONPATH=/home/appuser/.local/lib/python3.9/site-packages

# Set working directory
WORKDIR /app

# Copy installed packages from builder stage
COPY --from=builder /root/.local /home/appuser/.local

# Ensure user can access .local directory
RUN chown -R appuser:appgroup /home/appuser/.local

# Copy application code
COPY . .

# Create cache directory with proper permissions and make start.sh executable
RUN mkdir -p /.legislatie_cache && \
    chown -R appuser:appgroup /.legislatie_cache && \
    chmod 755 /.legislatie_cache && \
    chmod +x start.sh

# Switch to non-root user
USER appuser

# Add user's local bin to PATH
ENV PATH="/home/appuser/.local/bin:$PATH"

# Verify Python packages are accessible
RUN python -c "import streamlit; import zeep; import diskcache; print('Dependencies verified')"

# Expose Streamlit port
EXPOSE 9090
EXPOSE 8501

# Health check for application
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import legislatie_client, cache, config; print('ok')"

# Default command: run Streamlit app
CMD ["./start.sh"]

# ===== DEVELOPMENT STAGE (optional) =====
# To use: docker build --target=development -t legislatie-dev .
FROM runtime AS development

# Install development dependencies
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    vim \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install pytest for testing
RUN pip install --user pytest pytest-mock pytest-asyncio

USER appuser

# Override command for development (interactive shell)
CMD ["/bin/bash"]
