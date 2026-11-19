FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV MONGO_HOST=host.docker.internal
ENV MONGO_PORT=27017
ENV MONGO_TLS=false
ENV DB_NAME=lab_12

CMD ["python", "run_all_lab12.py"]