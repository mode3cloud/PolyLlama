# Use a minimal Python 3.10 environment for reduced image size.
FROM python:3.10-slim

# Install required system packages:
# - git: for version control operations.
# - brotli: compression utility.
# - gcc, python3-dev: for building Python packages with native extensions.
RUN apt-get update && apt-get install -y git brotli gcc python3-dev && rm -rf /var/lib/apt/lists/*

# Install Python dependencies:
# - olah: main application.
# - brotli: Python bindings for Brotli compression.
RUN pip install --no-cache-dir olah brotli

# Set the working directory to /app.
WORKDIR /app

# Copy the Olah configuration file from the host to the container.
COPY ./olah-config.toml /app/config/config.toml

# Expose port 8090 for external access to the application.
EXPOSE 8090

# Set the default entrypoint to run olah-cli with the specified configuration file.
ENTRYPOINT ["olah-cli", "-c", "/app/config/config.toml"]