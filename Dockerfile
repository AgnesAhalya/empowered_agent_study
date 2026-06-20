FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY problems ./problems
COPY frontend ./frontend

RUN mkdir -p logs submissions

EXPOSE 8000

CMD ["python", "-m", "app.main"]