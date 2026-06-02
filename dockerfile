# Use a lightweight Python base image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the Python script
COPY app.py .

# Create a data directory for the persistent JSON database
RUN mkdir /data

# Expose the port the Flask app runs on
EXPOSE 5000

# Command to run the app
CMD ["python", "app.py"]
