FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV MONGO_URI=mongodb://host.docker.internal:27017/?maxPoolSize=10
ENV DB_NAME=lab_16

CMD ["python", "run_all_lab16.py"]