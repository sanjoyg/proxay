# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the requirements file into the container at /usr/src/app
COPY requirements.txt ./

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code into the container
COPY . .

# Set the python path to include the src directory
ENV PYTHONPATH /usr/src/app/src

# The default command to run when starting the container.
# The user will need to append the proxay arguments.
ENTRYPOINT ["python", "-m", "proxay.cli"]

# Example:
# docker build -t proxay .
# docker run --rm -it --network=host proxay --mode record --host http://host.docker.internal:8080 --tapes-dir my-tapes
