---
project: ki-knowledge
agent_project: ki-knowledge
scope: deployment
created: "2026-10-31 02"
updated: "2026-11-08 01"
update_reason: "Falsche normalize- und Manifestbeispiele archiviert"
status: active
---

# Deployment Stages - Detailed Guide

> **Warnung:** Die Stage-Angaben und übrigen Beispiele müssen noch überprüft
> werden. Die [Fehlannahmen zu normalize](archiv/NORMALIZE_FEHLANNAHMEN.md)
> sind archiviert; der Befehl erzeugt keine Deployment-Manifeste.

Reference guide for each deployment stage in ki-knowledge.

## Quick Comparison

| Aspect | dev-lokal | dev-mk | prod-k8s | prod |
|--------|-----------|--------|----------|------|
| **LLM** | Ollama local | Ollama in-cluster | Company KI | Company KI |
| **Database** | Postgres container | K8s Postgres | K8s Postgres | Postgres container |
| **Debug** | true | false | false | false |
| **Host** | Your machine | Minikube | K8s cluster | Ubuntu host |
| **Network** | localhost | Service discovery | Ingress | Localhost + Nginx |

---

## dev-lokal: Local Development

**Primary use**: Developer workstations with Docker installed.

### Configuration

```yaml
# config/stages/dev-lokal.yaml
llm:
  provider: ollama
apps:
  ki_knowledge:
    django:
      debug: true
      allowed_hosts: ["*"]
```

### Infrastructure

```
Your Computer
├── Docker Daemon
│   ├── postgres:14 (volume: ki-knowledge_pg_data)
│   ├── ollama (volume: ki-knowledge_ollama_models)
│   ├── ki-knowledge-api (port 8090, fastapi/uvicorn)
│   └── ki-knowledge-django (port 8000, runserver)
└── Ollama running locally
```

### Setup

```bash
# Ensure Docker is running
docker ps

# Set stage
export KI_STAGE=dev-lokal

# Start stack
cd /home/flow/dev_flow/ki-knowledge
stackctl -t local start

# Check status
stackctl -t local status
```

Expected output:
```
ki-knowledge (lokal)
  postgres  running    :5432  PID -  http://127.0.0.1:5432/
  ollama    running    :11434  PID -  http://127.0.0.1:11434/api/tags
  api       running    :8090  PID 12345  http://127.0.0.1:8090/docs
  django    foreign    :8000  PID 67890  http://127.0.0.1:8000/
```

### LLM Usage

Ollama runs locally. Models are downloaded/cached on first use.

```bash
# Check available models
curl http://127.0.0.1:11434/api/tags

# Pull a model (if not present)
ollama pull llama3.2

# Chat (manual testing)
curl http://127.0.0.1:11434/api/generate -d '{
  "model": "llama3.2",
  "prompt": "Hello"
}'
```

### Development Workflow

1. **Code changes**: Edit code, auto-reload works (both API and Django in debug mode)
2. **Database changes**: Migrations auto-run
3. **Model changes**: Restart Ollama or pull new models
4. **Full stack restart**: `stackctl -t local restart`

### Health Checks

```bash
# API is responsive?
curl http://127.0.0.1:8090/docs

# Django is running?
curl http://127.0.0.1:8000/

# Postgres is available?
psql -h 127.0.0.1 -U ki_knowledge -d ki_knowledge -c "SELECT version();"

# Ollama is responding?
curl http://127.0.0.1:11434/api/tags | jq .
```

### Common Issues

**"Port 8090 already in use"**:
```bash
# Find what's using it
lsof -i :8090
# Kill if needed
kill <PID>
```

**"Ollama not responding"**:
```bash
# Check if container exists
docker ps | grep ollama

# Restart it
stackctl -t local restart
```

**"Database connection refused"**:
```bash
# Ensure postgres container is up
docker ps | grep postgres
stackctl -t local status
```

---

## dev-mk: Minikube Kubernetes Development

**Primary use**: Test Kubernetes deployments locally before pushing to prod cluster.

### Configuration

```yaml
# config/stages/dev-mk.yaml
llm:
  provider: ollama
apps:
  ki_knowledge:
    django:
      debug: false
      allowed_hosts: ["*"]
```

### Infrastructure

```
Minikube K8s Cluster (minikube -p ki-knowledge)
├── Namespace: ki-knowledge
├── Deployment: ki-knowledge-app (django + api)
│   └── Pod: ki-knowledge-app-xxxxx (2 containers)
├── StatefulSet: postgres
│   └── Pod: postgres-0
├── Deployment: ollama
│   └── Pod: ollama-xxxxx
└── Service: ki-knowledge (ClusterIP/NodePort)
```

### Setup

```bash
# Ensure Minikube is installed
minikube version

# Start Minikube (creates profile ki-knowledge)
minikube start -p ki-knowledge --cpus=4 --memory=8192

# Set stage
export KI_STAGE=dev-mk

# Deploy
cd /home/flow/dev_flow/ki-knowledge
stackctl -t minikube start

# Check status
stackctl -t minikube status
```

### Service Discovery

Services are accessed via Kubernetes DNS (in-cluster):

- **Ollama**: `http://ollama:11434` (from app pod)
- **Postgres**: `postgres.ki-knowledge.svc.cluster.local:5432`
- **Swagger API**: `http://ki-knowledge:8090/docs` (NodePort or port-forward)

### Port Forward (for local testing)

```bash
# Forward API port
kubectl -n ki-knowledge port-forward svc/ki-knowledge 8090:8090

# Forward Postgres
kubectl -n ki-knowledge port-forward svc/postgres 5432:5432

# Then access as if on localhost
curl http://localhost:8090/docs
```

### Health Checks

```bash
# Are all pods running?
kubectl -n ki-knowledge get pods

# Are services available?
kubectl -n ki-knowledge get svc

# Check app logs
kubectl -n ki-knowledge logs deployment/ki-knowledge-app

# Check Ollama in cluster
kubectl -n ki-knowledge exec -it deployment/ki-knowledge-app -- \
  curl http://ollama:11434/api/tags
```

### Common Issues

**"Cluster stopped"**:
```bash
stackctl -t minikube status  # Shows "Cluster gestoppt"
minikube start -p ki-knowledge
stackctl -t minikube start
```

**"OOMKilled pods"**:
```bash
# Increase Minikube memory
minikube delete -p ki-knowledge
minikube start -p ki-knowledge --memory=12288
```

**"Image pull errors"**:
```bash
# Minikube uses its own Docker daemon, tag images appropriately
eval $(minikube docker-env -p ki-knowledge)
docker build -t ki-knowledge:latest .
```

---

## prod-k8s: Production Kubernetes

**Primary use**: Cloud deployment (EKS, GKE, etc.).

### Configuration

```yaml
# config/stages/prod-k8s.yaml
llm:
  provider: ki
http:
  request_timeout: 120
apps:
  ki_knowledge:
    django:
      debug: false
```

### Infrastructure

```
Production Kubernetes Cluster
├── Namespace: ki-knowledge
├── Deployment: ki-knowledge (django + api, replicas: 3)
├── StatefulSet: postgres (replicas: 1, PVC for data)
├── Deployment: ollama (replicas: 1, PVC for models)
├── Service: ki-knowledge (ClusterIP)
├── Ingress: ki-knowledge.company.com
├── ConfigMap: config-merged (resolved ki.yaml)
├── Secret: creds (from creds.yaml)
└── HPA: Auto-scale based on CPU/memory
```

### Deployment via Helm/Kustomize

Configuration comes from:

```bash
# 1. Base K8s manifests define structure
# 2. config/stages/prod-k8s.yaml → ConfigMap
# 3. creds.yaml → Secret
# 4. Merged config used by pods via volume mount
```

Für den tatsächlichen Deploymentablauf die führende stackctl-Dokumentation
verwenden. Der frühere Befehl zur angeblichen Manifest-Erzeugung war falsch.

### LLM Provider (Company KI)

Unlike dev stages, prod uses Company KI API:

```yaml
llm:
  provider: ki
  providers:
    ki:
      base_url: https://ki.company.com/api
      api_key: <from creds.yaml>
      model: default
```

API key must be in `creds.yaml` (mounted as Secret).

### Networking

- **Ingress**: `ki-knowledge.company.com`
- **Internal DNS**: `ki-knowledge.ki-knowledge.svc.cluster.local`
- **External**: Only through Ingress with TLS

### Monitoring

```bash
# Check pod status
kubectl -n ki-knowledge get pods -o wide

# Check logs (all replicas)
kubectl -n ki-knowledge logs -l app=ki-knowledge --tail=100

# Check resource usage
kubectl -n ki-knowledge top pods

# Check config applied
kubectl -n ki-knowledge get configmap ki-config -o yaml
```

### Scaling

```bash
# Manual scale
kubectl -n ki-knowledge scale deployment ki-knowledge --replicas=5

# Check HPA status
kubectl -n ki-knowledge get hpa

# View HPA behavior
kubectl -n ki-knowledge describe hpa ki-knowledge-hpa
```

---

## prod: Production Host (Systemd + Docker Compose)

**Primary use**: Self-hosted production on Ubuntu server.

### Configuration

```yaml
# config/stages/prod.yaml
llm:
  provider: ki
http:
  request_timeout: 120
apps:
  ki_knowledge:
    django:
      debug: false
stack:
  services:
    api:
      env: {UVICORN_RELOAD: "false"}
    django:
      host: 0.0.0.0
```

### Infrastructure

```
Ubuntu Server (production.example.com)
├── Systemd Services
│   ├── ki-knowledge-api.service
│   └── ki-knowledge-django.service
├── Docker Compose
│   ├── postgres:14
│   ├── ollama
│   └── redis (optional cache)
├── Nginx (reverse proxy)
│   └── ki-knowledge.example.com
└── SSL/TLS (Let's Encrypt)
```

### Deployment

1. **Prepare server**:
```bash
# SSH into server
ssh deploy@production.example.com

# Install dependencies
sudo apt-get update
sudo apt-get install docker.io docker-compose systemd

# Clone repository
git clone https://github.com/company/ki-knowledge.git
cd ki-knowledge
```

2. **Configure for production**:
```bash
# Set stage
echo "prod" > config/stages/.active_stage

# Copy/prepare creds.yaml (secrets)
cp creds.yaml.example creds.yaml
# Edit creds.yaml with real secrets

# Prepare ki.yaml with host-specific values
vim ki.yaml
# - Set allowed_hosts to ["ki-knowledge.example.com"]
# - Set database DSN to production Postgres
# - Set secret_key to random secure value
```

3. **Start services**:
```bash
# Start Docker Compose (postgres, ollama, redis)
docker-compose -f docker-compose.prod.yaml up -d

# Create systemd units
sudo systemctl enable ki-knowledge-api.service
sudo systemctl enable ki-knowledge-django.service

sudo systemctl start ki-knowledge-api.service
sudo systemctl start ki-knowledge-django.service

# Check status
sudo systemctl status ki-knowledge-api
sudo systemctl status ki-knowledge-django
```

4. **Setup reverse proxy (Nginx)**:
```bash
# Copy Nginx config
sudo cp nginx.conf.prod /etc/nginx/sites-available/ki-knowledge
sudo ln -s /etc/nginx/sites-available/ki-knowledge /etc/nginx/sites-enabled/

# Enable SSL (Let's Encrypt)
sudo certbot certonly --standalone -d ki-knowledge.example.com
sudo certbot install --installer nginx -d ki-knowledge.example.com

# Reload Nginx
sudo systemctl reload nginx
```

### Monitoring

```bash
# Check services
sudo systemctl status ki-knowledge-*

# View logs (journalctl)
sudo journalctl -u ki-knowledge-api -f   # Follow API logs
sudo journalctl -u ki-knowledge-django -f

# Check Docker containers
docker-compose -f docker-compose.prod.yaml ps

# Check Nginx
sudo systemctl status nginx
sudo tail -f /var/log/nginx/error.log
```

### Updates

```bash
# Pull latest code
git pull origin main

# Rebuild if needed
docker-compose -f docker-compose.prod.yaml down
docker-compose -f docker-compose.prod.yaml up -d

# Restart services
sudo systemctl restart ki-knowledge-api
sudo systemctl restart ki-knowledge-django

# Verify
curl https://ki-knowledge.example.com/
```

### Backups

```bash
# Backup database
docker-compose -f docker-compose.prod.yaml exec postgres \
  pg_dump -U ki_knowledge ki_knowledge > backup-$(date +%Y%m%d).sql

# Backup Ollama models
tar czf ollama-models-backup-$(date +%Y%m%d).tar.gz \
  /var/lib/docker/volumes/ki-knowledge_ollama_models/_data
```

---

## Switching Between Stages

### Method 1: Environment Variable (Recommended for CI/CD)

```bash
# For current shell session
export KI_STAGE=prod
stackctl -t local status

# For one command
KI_STAGE=dev-mk stackctl -t minikube status
```

### Method 2: Marker File (Recommended for persistent host config)

```bash
# Set default stage for the machine
echo "prod" > config/stages/.active_stage

# Verify
cat config/stages/.active_stage

# Use stackctl
stackctl -t local status  # Uses stage from marker
```

### Method 3: Via Code

```python
import os
os.environ['KI_STAGE'] = 'prod'

from ki_core.config import load_config
config = load_config()
print(config.get_path('llm.provider'))  # prod uses "ki"
```

---

## Stage-Specific Validation

Before deploying to a new stage, validate:

```bash
# Historisches Beispiel; API und benötigte Werte sind noch zu prüfen.
python -c "
from ki_core.config import load_config
c = load_config()
assert c.get_path('apps.ki_knowledge.django.secret_key'), 'secret_key not set!'
assert c.get_path('llm.providers.ki.api_key'), 'KI API key not set!'
print('✓ All required fields present')
"
```

---

## References

- **Main Config**: `ki.yaml`
- **Secrets**: `creds.yaml`
- **Stage Files**: `config/stages/*.yaml`
- **Main Docs**: [README.md](README.md)
- **Config Reference**: [CONFIG_MERGE_REFERENCE.md](CONFIG_MERGE_REFERENCE.md)
