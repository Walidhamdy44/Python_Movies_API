FROM python:3.11-slim

# Install Chrome and dependencies for SeleniumBase
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome
RUN wget -q -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get update \
    && apt-get install -y /tmp/chrome.deb \
    && rm /tmp/chrome.deb \
    && rm -rf /var/lib/apt/lists/*

# Set display for headless
ENV DISPLAY=:99

# Set working directory
WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install SeleniumBase drivers
RUN seleniumbase install chromedriver

# Copy app code
COPY . .

# Expose port
EXPOSE 8000

# Environment variables (can be overridden at runtime)
ENV AUTH_ENABLED=false
ENV API_KEY=""

# Run the app
CMD uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}
