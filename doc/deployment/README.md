# Deployment Architecture

This directory documents the deployment infrastructure for ki-knowledge.

## Quick Links

- **[Ollama: Server-Anforderungen](OLLAMA_REQUIREMENTS.md)** - Dedizierter Inferenzhost, Hardwareprofile und messbare Leistungsziele.
- **[Uberspace 7: Umsetzung und Installation](UBERSPACE7_IMPLEMENTATION.md)** - Bootstrap, supervisord, PostgreSQL/pgvector und Git-Updates; Hostabnahme offen.
- **[Uberspace 8: Umsetzungsplan](UBERSPACE8_IMPLEMENTATION.md)** - Rootloses Hosting, stackctl/systemd-Grenzen und geplante Skripte; noch nicht implementiert.
- **[CONFIG_MERGE_REFERENCE.md](CONFIG_MERGE_REFERENCE.md)** - How configuration layers work
- **[STAGES.md](STAGES.md)** - Detailed guide for each deployment stage
- **[TESTING.md](TESTING.md)** - Testing deployment configurations locally

## Overview

ki-knowledge supports multiple deployment scenarios:

| Scenario | Stage | Infrastructure | Use Case |
|----------|-------|-----------------|----------|
| **Local Development** | `dev-lokal` | Docker Compose on Host | Developer workstation |
| **K8s Development** | `dev-mk` | Minikube | Test K8s changes locally |
| **Production K8s** | `prod-k8s` | Kubernetes Cluster | Cloud/Enterprise deployment |
| **Production Host** | `prod` | Ubuntu + Docker Compose | Self-hosted deployment |

## Configuration

All configuration is managed through layered YAML files:

```
config/
├── stages/            # Environment-specific overrides
│   ├── dev-lokal.yaml
│   ├── dev-mk.yaml
│   ├── prod-k8s.yaml
│   └── prod.yaml
├── profiles/          # Optional profile-specific config
├── defaults/          # Fallback defaults
└── runtime/           # Host-local overrides (not version-controlled)
```

To activate a stage:
```bash
export KI_STAGE=dev-lokal
# or place "dev-lokal" in config/stages/.active_stage
```

## Getting Started

1. **Read this first**: [CONFIG_MERGE_REFERENCE.md](CONFIG_MERGE_REFERENCE.md)
   - Understand how configurations are layered and merged
   - Learn the priority order
   - See examples of correct vs. incorrect stage definitions

2. **Deploy locally**:
   ```bash
   export KI_STAGE=dev-lokal
   stackctl -t local start
   stackctl -t local status
   ```

3. **Test configuration**:
   ```bash
   export KI_STAGE=dev-lokal
   stackctl -t local normalize  # Validate and print merged config
   ```

## Key Concepts

### Stages (Environments)

Only **one stage** is active at a time. Stages provide environment-specific overrides:

- **dev-lokal**: Ollama for LLM, Django debug=true, * allowed_hosts
- **dev-mk**: Minikube K8s, in-cluster Ollama, debug=false
- **prod-k8s**: Production K8s, company KI provider
- **prod**: Production host, company KI provider, optimized settings

### Configuration Precedence

1. **creds.yaml** (secrets, always merged last)
2. **Environment variables** (KI_CFG_* prefix)
3. **Runtime config** (host-local overrides)
4. **Active Stage** (stage-specific)
5. **Active Profile** (optional profile)
6. **Main config** (ki.yaml)
7. **Defaults** (config/defaults/)
8. **Schema defaults** (built-in)

### Provider Detection

The system includes intelligent LLM provider selection:

```python
cm = ConfigManager()
provider = cm.get_llm_provider()  # Returns best available: openai > ollama > ki > mock
```

This is NOT just reading `llm.provider` from config - it checks availability.

## Infrastructure

### dev-lokal

```
Docker Host
├── postgres:14 (port 5432)
├── ollama (port 11434)
├── ki-knowledge-api (port 8090)
└── ki-knowledge-django (port 8000, foreign)
```

Start:
```bash
export KI_STAGE=dev-lokal
stackctl -t local start
stackctl -t local status
```

Health check:
```bash
curl http://127.0.0.1:8090/docs  # API is up?
curl http://127.0.0.1:8000/       # Django is up?
```

### prod-k8s

```
Kubernetes Cluster (prod)
├── Namespace: ki-knowledge
├── Pod: app (django + api)
├── Pod: postgres (Postgres)
├── Pod: ollama (Embeddings)
└── Ingress: ki-knowledge.example.com
```

Deploy:
```bash
export KI_STAGE=prod-k8s
stackctl -t k8s start
```

### prod (Host)

```
Ubuntu Host
├── Systemd Service: ki-knowledge-api
├── Systemd Service: ki-knowledge-django
├── Docker Container: postgres
├── Docker Container: ollama
└── Nginx: reverse proxy
```

## Troubleshooting

**"Stage not found"**:
```bash
export KI_STAGE=dev-lokal  # Make sure env var is set
stackctl -t local status
```

**"Config validation failed"**:
```bash
# Check merged config
stackctl -t local normalize > /tmp/merged-config.yaml
# Review for invalid values
```

**"Provider detection failing"**:
```python
from ki_core.config import ConfigManager
cm = ConfigManager()
print(cm.load().get_path("llm.provider"))        # Raw config
print(cm.get_llm_provider())                     # Detected provider
```

## Next Steps

1. **For local development**: Go to [CONFIG_MERGE_REFERENCE.md](CONFIG_MERGE_REFERENCE.md)
2. **For K8s deployment**: See [STAGES.md](STAGES.md) - prod-k8s section
3. **For testing changes**: See [TESTING.md](TESTING.md)

## References

- **Project Root**: `/home/flow/dev_flow/ki-knowledge/`
- **Config Directory**: `config/`
- **Main Config**: `ki.yaml`
- **Secrets**: `creds.yaml` (.gitignored)
- **App Source**: `ki_knowledge/`
- **API Source**: `ki/api/`
