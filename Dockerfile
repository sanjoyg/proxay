# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Install pipenv
RUN pip install pipenv

# Copy the dependency files to the working directory
COPY Pipfile Pipfile.lock ./

# Install project dependencies
# --system: Install dependencies to the system site-packages
# --deploy: Ensure Pipfile.lock is up-to-date and fail if it is not
# --ignore-pipfile: Lock file is mandatory
RUN pipenv install --system --deploy --ignore-pipfile

# Copy the rest of the application's source code from the host to the container
COPY src/ ./src/

# The command to run when the container starts.
# This is a placeholder; the actual command with arguments will be provided
# by docker-compose.
ENTRYPOINT ["python", "src/cli.py"]
