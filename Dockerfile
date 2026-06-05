FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Add non-root user
RUN adduser --disabled-password --home /home/django-user django-user

# Set workdir
WORKDIR /app

# Copy code and set permissions
COPY . /app/
RUN chown -R django-user:django-user /app

# Switch to non-root user
USER django-user

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt