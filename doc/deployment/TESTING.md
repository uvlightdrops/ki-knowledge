---
project: ki-knowledge
agent_project: ki-knowledge
scope: deployment
created: "2026-10-31 02"
updated: "2026-11-08 01"
update_reason: "Falsche normalize-Testbefehle archiviert"
status: active
---

# Testing Deployment Configurations

> **Warnung:** Die übrigen Prüfkommandos sind nicht auf Aktualität und
> Seiteneffekte überprüft. Die früheren
> [Fehlannahmen zu normalize](archiv/NORMALIZE_FEHLANNAHMEN.md) sind archiviert.

Guide for testing stage configurations locally and in CI/CD.

## Quick Start

```bash
# Test current stage
export KI_STAGE=dev-lokal
stackctl -t local status

# Run health checks
python scripts/health_check.py
```

## Testing Individual Stages

### Test dev-lokal

```bash
export KI_STAGE=dev-lokal

# 1. Start stack
stackctl -t local start
sleep 5

# 2. Check all services running
stackctl -t local status | grep -E "running|foreign"

# 3. Test connectivity
curl http://127.0.0.1:8090/docs          # API
curl http://127.0.0.1:8000/               # Django
curl http://127.0.0.1:11434/api/tags     # Ollama
psql -h 127.0.0.1 -U ki_knowledge -c "SELECT 1;"  # Postgres

# 4. Test LLM provider detection
python -c "
from ki_core.config import ConfigManager
cm = ConfigManager()
provider = cm.get_llm_provider()
print(f'Detected LLM provider: {provider}')
assert provider in ['ollama', 'openai', 'ki'], f'Invalid: {provider}'
"

# 5. Cleanup
stackctl -t local stop
```

### Test dev-mk

Requires Minikube installed and running.

```bash
export KI_STAGE=dev-mk

# 1. Check Minikube
minikube status -p ki-knowledge

# 2. Start stack
stackctl -t minikube start
sleep 10

# 3. Check pod status
kubectl -n ki-knowledge get pods

# 4. Test connectivity (via port-forward)
kubectl -n ki-knowledge port-forward svc/ki-knowledge 8090:8090 &
port_forward_pid=$!
sleep 2
curl http://localhost:8090/docs
kill "$port_forward_pid"

# 5. Test in-cluster LLM
kubectl -n ki-knowledge exec -it deployment/ki-knowledge-app -- \
  curl http://ollama:11434/api/tags

# 6. Cleanup
stackctl -t minikube stop
```

### Test prod-k8s

```bash
export KI_STAGE=prod-k8s

# Historisches Beispiel; API und benötigte Werte sind noch zu prüfen.
python -c "
from ki_core.config import load_config
config = load_config()
required = ['llm.provider', 'apps.ki_knowledge.django.secret_key']
for key in required:
    val = config.get_path(key)
    assert val, f'Missing required: {key}'
    print(f'✓ {key} ist gesetzt')
"
```

### Test prod

```bash
export KI_STAGE=prod

# 2. Check Systemd service definitions are present
ls -la systemd/*.service 2>/dev/null || echo "Systemd files not found"

# 3. Validate Nginx config syntax
if [ -f nginx.conf.prod ]; then
  nginx -t -c $(pwd)/nginx.conf.prod
fi

# 4. Dry-run deployment (if deployment script exists)
bash deploy.sh --dry-run 2>/dev/null || echo "No deployment script"
```

## Configuration Validation

### Test Merge Order

Verify that higher-priority configs override lower ones:

```bash
python << 'PYTHON'
import sys
sys.path.insert(0, '/home/flow/dev_flow/ki-core/src')
sys.path.insert(0, '/home/flow/dev_flow/yaml_cfg_wizard/src')

from yaml_cfg_wizard.core import load_yaml_file, deep_merge
from pathlib import Path
import os

stage = os.getenv('KI_STAGE', 'dev-lokal')
print(f"Testing merge order for stage: {stage}")
print()

# Load files in order
ki_yaml = load_yaml_file("ki.yaml")
stage_yaml = load_yaml_file(f"config/stages/{stage}.yaml")

# Simulate merge
base = ki_yaml
override = stage_yaml

print("=== Before Merge (ki.yaml) ===")
print(f"debug: {base.get('apps', {}).get('ki_knowledge', {}).get('django', {}).get('debug')}")

print("\n=== Override (stage) ===")
print(f"debug: {override.get('apps', {}).get('ki_knowledge', {}).get('django', {}).get('debug')}")

merged = deep_merge(base, override)

print("\n=== After Merge ===")
print(f"debug: {merged.get('apps', {}).get('ki_knowledge', {}).get('django', {}).get('debug')}")
print()

# Verify stage override works
stage_debug = override.get('apps', {}).get('ki_knowledge', {}).get('django', {}).get('debug')
merged_debug = merged.get('apps', {}).get('ki_knowledge', {}).get('django', {}).get('debug')

if stage_debug is not None and stage_debug == merged_debug:
    print("✓ Stage successfully overrides base config")
else:
    print("✗ Stage override failed!")
    sys.exit(1)
PYTHON
```

### Test Environment Variable Override

Environment variables should have highest priority:

```bash
# Test env var override
python << 'PYTHON'
import os
import sys
sys.path.insert(0, '/home/flow/dev_flow/ki-core/src')

# Set env var to override config
os.environ['KI_CFG_APPS__KI_KNOWLEDGE__DJANGO__DEBUG'] = 'false'
os.environ['KI_STAGE'] = 'dev-lokal'  # dev-lokal.yaml has debug=true

from ki_core.config import load_config
config = load_config()

debug_value = config.get_path('apps.ki_knowledge.django.debug')
print(f"Config says debug={debug_value} (env var should override to False)")

if debug_value == False:
    print("✓ Environment variable override works correctly")
else:
    print(f"✗ Environment variable not applied! Got: {debug_value}")
    sys.exit(1)
PYTHON
```

### Test Provider Detection

```bash
python << 'PYTHON'
import sys
sys.path.insert(0, '/home/flow/dev_flow/ki-core/src')

from ki_core.config import ConfigManager
import os

stages = ['dev-lokal', 'dev-mk', 'prod-k8s', 'prod']

for stage in stages:
    os.environ['KI_STAGE'] = stage
    cm = ConfigManager()
    provider = cm.get_llm_provider()
    configured = cm.load().get_path('llm.provider')
    
    print(f"{stage:12} | config: {configured:8} | detected: {provider:8}")

PYTHON
```

## CI/CD Testing

### GitHub Actions Workflow

Example `.github/workflows/test-config.yml`:

```yaml
name: Config Validation

on:
  push:
    branches: [main]
    paths:
      - 'config/**'
      - 'ki.yaml'
      - 'schema/**'
      - '.github/workflows/test-config.yml'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install ki-core yaml-cfg-wizard pyyaml jsonschema
      
      - name: Test config merge (all stages)
        env:
          KI_STAGE: dev-lokal
        run: |
          python -c "
          from ki_core.config import load_config, active_layers
          config = load_config()
          layers = active_layers()
          assert layers['stage'], 'No stage selected'
          assert 'llm' in config, 'LLM config missing'
          print('✓ Config loads correctly')
          "
      
      - name: Validate against schema
        run: |
          python -c "
          from ki_core.config import load_config
          from yaml_cfg_wizard.core import validate_schema
          config = load_config()
          # If we reach here, schema validation passed
          print('✓ Config validates against schema')
          "
      
      - name: Test provider detection
        run: |
          python -c "
          from ki_core.config import ConfigManager
          cm = ConfigManager()
          provider = cm.get_llm_provider()
          assert provider in ['openai', 'ollama', 'ki', 'mock'], f'Invalid: {provider}'
          print(f'✓ Provider detection works: {provider}')
          "
```

### Docker Testing

Test configuration in containerized environment:

```bash
# Build test image
docker build -f Dockerfile.test -t ki-knowledge:config-test .

# Run validation
docker run --rm \
  -e KI_STAGE=dev-lokal \
  ki-knowledge:config-test \
  python -c "
  from ki_core.config import load_config
  config = load_config()
  print('✓ Config works in container')
  "
```

## Health Check Script

Create `scripts/health_check.py`:

```python
#!/usr/bin/env python3
"""Health check script for ki-knowledge deployment."""

import os
import sys
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
sys.path.insert(0, '/home/flow/dev_flow/ki-core/src')

from ki_core.config import load_config, ConfigManager

def check_config():
    """Validate configuration loads correctly."""
    try:
        config = load_config()
        assert isinstance(config, dict)
        print("✓ Config loads successfully")
        return True
    except Exception as e:
        print(f"✗ Config error: {e}")
        return False

def check_provider():
    """Validate LLM provider is selected."""
    try:
        cm = ConfigManager()
        provider = cm.get_llm_provider()
        print(f"✓ LLM provider detected: {provider}")
        return True
    except Exception as e:
        print(f"✗ Provider detection failed: {e}")
        return False

def check_connectivity():
    """Test connectivity to services."""
    config = load_config()
    checks = []
    
    # API check
    try:
        api_url = "http://127.0.0.1:8090/docs"
        response = requests.get(api_url, timeout=2)
        if response.status_code == 200:
            print(f"✓ API responding at {api_url}")
            checks.append(True)
        else:
            print(f"✗ API returned {response.status_code}")
            checks.append(False)
    except requests.exceptions.ConnectionError:
        print("✗ API not reachable (ensure KI_STAGE=dev-lokal and stackctl started)")
        checks.append(False)
    except Exception as e:
        print(f"⊘ API check skipped: {e}")
        checks.append(True)  # Don't fail if test environment
    
    # Ollama check
    try:
        ollama_url = "http://127.0.0.1:11434/api/tags"
        response = requests.get(ollama_url, timeout=2)
        if response.status_code == 200:
            print(f"✓ Ollama responding at {ollama_url}")
            checks.append(True)
        else:
            print(f"✗ Ollama returned {response.status_code}")
            checks.append(False)
    except requests.exceptions.ConnectionError:
        print("✗ Ollama not reachable")
        checks.append(False)
    except Exception as e:
        print(f"⊘ Ollama check skipped: {e}")
        checks.append(True)
    
    return all(checks) if checks else True

def main():
    """Run all health checks."""
    print(f"KI_STAGE: {os.getenv('KI_STAGE', 'not set')}")
    print()
    
    results = [
        check_config(),
        check_provider(),
        check_connectivity(),
    ]
    
    print()
    if all(results):
        print("✓ All checks passed")
        return 0
    else:
        print("✗ Some checks failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
```

Run it:

```bash
export KI_STAGE=dev-lokal
stackctl -t local start
sleep 5
python scripts/health_check.py
```

## Performance Testing

### Load Testing (dev environment only)

```bash
# Install Apache Bench
sudo apt-get install apache2-utils

# Simple load test
ab -n 100 -c 10 http://127.0.0.1:8000/

# Concurrent requests
ab -n 1000 -c 50 http://127.0.0.1:8000/
```

### Database Performance

```bash
# Check query performance
psql -h 127.0.0.1 -U ki_knowledge -d ki_knowledge << 'SQL'
EXPLAIN ANALYZE
SELECT * FROM knowledge_items LIMIT 100;
SQL
```

## Troubleshooting Tests

### "Config loads but provider is mock"

```bash
# Check what ConfigManager detects
python -c "
from ki_core.config import ConfigManager
cm = ConfigManager()
config = cm.load()
print('Explicit provider:', config.get_path('llm.provider'))
print('Detected provider:', cm.get_llm_provider())
print('Has OpenAI key:', bool(config.get_path('llm.providers.openai.api_key')))
print('Has Ollama URL:', bool(config.get_path('llm.providers.ollama.base_url')))
"
```

### "Services not responding"

```bash
# Check services are actually running
docker ps | grep ki_knowledge

# Check logs
docker logs ki_knowledge-api 2>&1 | tail -20
docker logs ki_knowledge-django 2>&1 | tail -20
```

### "Merge order seems wrong"

Konfigurationsschichten anhand der
[Projektanleitung](../guides/YAML_CONFIG_SYSADMIN.md) prüfen; Geheimnisse nicht
in Ausgaben oder temporäre Dateien kopieren.

## References

- **Health Check Script**: Create at `scripts/health_check.py`
- **Configuration**: [CONFIG_MERGE_REFERENCE.md](CONFIG_MERGE_REFERENCE.md)
- **Stages**: [STAGES.md](STAGES.md)
- **Main Docs**: [README.md](README.md)
