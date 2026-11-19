# Lab 9: Write Concern Latency & Network Partition (Docker Hub Submission)

## 1. Build & Push to Docker Hub
```powershell
docker build -t <your-dockerhub-username>/nosql-lab-09:latest .
docker login
docker push <your-dockerhub-username>/nosql-lab-09:latest
```

## 2. Run for Demonstration
```powershell
docker run --rm -e MONGO_URI=mongodb://host.docker.internal:27017 <your-dockerhub-username>/nosql-lab-09:latest
```

## Live Web Interface
- **Live CTI Sentinel Dashboard:** [http://127.0.0.1:8080/?lab=9](http://127.0.0.1:8080/?lab=9)
