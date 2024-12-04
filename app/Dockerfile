# Temporary image to build the application
FROM python:3.11-slim-bookworm AS build-stage

# Configure Python to not buffer "stdout" or create .pyc files
ENV PYTHONBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Update apt and install gcc
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev

# Upgrade pip
RUN pip install pip --upgrade

# Upgrade setuptools
RUN pip install --upgrade setuptools

# Add a non-root user  
RUN adduser --disabled-login wmata
USER wmata
WORKDIR /home/wmata

# Create a virtual environment
RUN python -m venv /home/wmata/venv

# Add the virtual environment to the PATH
ENV PATH="/home/wmata/venv/bin:$PATH"

# Install dependencies
COPY --chown=wmata:wmata ./requirements/prod.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Final image
FROM python:3.11-slim-bookworm AS runtime-stage

# Copy the virtual environment from the previous image
COPY --from=build-stage /home/wmata/venv /home/wmata/venv

WORKDIR /home/wmata

# Add the virtual environment to the PATH
ENV PATH="/home/wmata/venv/bin:$PATH"

# Copy the application code
COPY --chown=wmata:wmata . /home/wmata/app

WORKDIR /home/wmata/app

# Run the app
CMD ["python3", "-u", "app.py"]