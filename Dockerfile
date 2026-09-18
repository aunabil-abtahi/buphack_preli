FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /app/

# Expose port
EXPOSE 8080

# Command to run the application using dynamic port
CMD sh -c "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"
