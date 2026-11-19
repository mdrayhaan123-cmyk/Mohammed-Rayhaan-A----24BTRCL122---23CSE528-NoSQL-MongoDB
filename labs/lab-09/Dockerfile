FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir pymongo rich python-dotenv

COPY . .

ENV PYTHONUNBUFFERED=1

CMD ["python", "run_all_lab9.py"]
