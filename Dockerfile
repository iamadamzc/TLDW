FROM python:3.11-slim

WORKDIR /app

# Install minimal dependencies
RUN pip install flask gunicorn

# Copy test app
COPY test-app.py app.py

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "app:app"]