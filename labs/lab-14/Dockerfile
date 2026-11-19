FROM python:3.11-slim

# Install MongoDB Database Tools (mongodump & mongorestore) for Lab 14.2
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && \
    ARCH=$(dpkg --print-architecture) && \
    if [ "$ARCH" = "amd64" ]; then TOOLS_ARCH="x86_64"; else TOOLS_ARCH="aarch64"; fi && \
    curl -fsSL "https://fastdl.mongodb.org/tools/db/mongodb-database-tools-debian12-${TOOLS_ARCH}-100.10.0.tgz" -o /tmp/tools.tgz && \
    tar -xzf /tmp/tools.tgz -C /tmp && \
    mv /tmp/mongodb-database-tools-*/bin/mongodump /usr/local/bin/ && \
    mv /tmp/mongodb-database-tools-*/bin/mongorestore /usr/local/bin/ && \
    rm -rf /tmp/tools.tgz /tmp/mongodb-database-tools-* && \
    apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Kerberos GSSAPI runtime required by mongodump/mongorestore
RUN apt-get update && apt-get install -y --no-install-recommends libgssapi-krb5-2 && rm -rf /var/lib/apt/lists/*

COPY . .

ENV PYTHONUNBUFFERED=1
ENV MONGO_URI=mongodb://host.docker.internal:27017/
ENV DB_NAME=lab_14
ENV BACKUP_DIR=/app/backups
ENV METRICS_LOG_PATH=/app/logs/metrics.log

CMD ["python", "run_all_lab14.py"]