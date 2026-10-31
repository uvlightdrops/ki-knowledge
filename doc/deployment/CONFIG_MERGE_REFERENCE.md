# Config Merge Reference: ki-knowledge Pattern

**Status**: ki-knowledge ist die REFERENZ-IMPLEMENTIERUNG für kicli-code-assist.

## Overview

ki-knowledge definiert wie **Stage-Konfiguration in einem yaml-cfg-wizard System** funktioniert. Diese Dokumentation hilft anderen Projekten (wie kicli-code-assist) das gleiche Verhalten zu erreichen.

## Configuration Resolution Order

Definiert in `ki_core/config.py:load_config()`. **WICHTIG**: Diese Reihenfolge ist nach Priorität (höchste zuerst):

```
1. creds.yaml (deep-merged on top für secrets)
2. Environment variables (KI_CFG_* prefix, __ für nesting)
3. Runtime file (config/runtime/runtime.yaml) - Host-lokale Overrides
4. Active STAGE (config/stages/<name>.yaml) - NUR eine Stage!
5. Active PROFILE (config/profiles/<name>.yaml) - NUR ein Profile!
6. Main config (ki.yaml)
7. Defaults (config/defaults/*.yaml)
8. Schema defaults (merged from all .schema.yaml files)
```

### Key Insight: Deep Merge Semantics

```python
def deep_merge(base: Any, override: Any) -> Any:
    if isinstance(base, dict) and isinstance(override, dict):
        result = deepcopy(base)
        for key, value in override.items():
            if key in result:
                result[key] = deep_merge(result[key], value)  # RECURSIV mergen!
            else:
                result[key] = deepcopy(value)
        return result
    return deepcopy(override)  # Non-dict values werden ÜBERSCHRIEBEN, nicht gemischt
```

**Kritischer Punkt**: Bei Non-Dict-Values (Strings, Bools, etc.) wird der Override-Wert vollständig übernommen. Bei Dicts wird rekursiv gemacht.

## ki-knowledge Stage Definitionen

### Current Stages

| Stage | Typ | LLM | Debug | Nutzung |
|-------|-----|-----|-------|---------|
| dev-lokal | Host | Ollama | true | Developer lokal-host (alle Docker/Postgres lokal) |
| dev-mk | Minikube | Ollama (in-cluster) | false | Developer Minikube (K8s lokal testen) |
| prod-k8s | Kubernetes | Company KI | false | Production K8s Cluster |
| prod | Host | Company KI | false | Production Ubuntu Host (Docker Compose + Systemd) |

### Aktuelle Stage-Definitionen

**dev-lokal.yaml**:
```yaml
llm:
  provider: ollama
apps:
  ki_knowledge:
    django:
      debug: true
      allowed_hosts: ["*"]
```

**dev-mk.yaml**:
```yaml
llm:
  provider: ollama
apps:
  ki_knowledge:
    django:
      debug: false
      allowed_hosts: ["*"]
```

**prod-k8s.yaml**:
```yaml
llm:
  provider: ki
http:
  request_timeout: 120
apps:
  ki_knowledge:
    django:
      debug: false
```

**prod.yaml**:
```yaml
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

## Selection Mechanism

Stages werden ausgewählt via:

1. **Environment Variable**: `export KI_STAGE=dev-lokal`
2. **Marker File**: `config/stages/.active_stage` containing "dev-lokal"

Profile funktionieren gleich:
1. **Environment Variable**: `export KI_PROFILE=myprofile`
2. **Marker File**: `config/profiles/.active_profile`

## Provider Detection Logic

**WICHTIG**: `ConfigManager.get_llm_provider()` ist NICHT einfach nur `config.llm.provider` lesen!

Es gibt intelligente Fallback-Logik:

```python
def get_llm_provider(self) -> str:
    # 1. Check explicit provider (if set to non-"auto")
    explicit = config.get_path("llm.provider", "auto").strip().lower()
    if explicit and explicit != "auto":
        return explicit
    
    # 2. Priority: OpenAI (if key exists)
    if has_openai_key_and_valid:
        return "openai"
    
    # 3. Priority: Ollama (if reachable)
    if ollama_url_reachable:
        return "ollama"
    
    # 4. Priority: Company KI (if key exists)
    if has_ki_key_and_valid:
        return "ki"
    
    # 5. Fallback: Mock
    return "mock"
```

**Implikation für kicli-code-assist**: 
- Stage kann `llm.provider: ollama` setzen
- Aber wenn creds.yaml einen OpenAI key hat, kann `get_llm_provider()` trotzdem "openai" returnieren
- Das ist DESIGN: Stages setzen Defaults, aber Provider-Detection nutzt was verfügbar ist

## Best Practices für Stage-Definitionen

### 1. Nur spezifische Overrides definieren

❌ **FALSCH**:
```yaml
# dev-lokal.yaml - viel zu viel!
llm:
  provider: ollama
  providers:
    ollama:
      base_url: http://localhost:11434
      model: llama3.2
    ki:
      base_url: ""
      api_key: ""
      model: ""
apps:
  ki_knowledge:
    django:
      db_path: ""
      secret_key: ""
      debug: true
      allowed_hosts: ["*"]
      wagtail_admin_base_url: ""
```

✅ **RICHTIG**:
```yaml
# dev-lokal.yaml - nur die Unterschiede!
llm:
  provider: ollama
apps:
  ki_knowledge:
    django:
      debug: true
      allowed_hosts: ["*"]
```

**Grund**: Deep merge bedeutet: alles andere kommt aus ki.yaml + defaults + creds.yaml.

### 2. Environment Overrides nutzen statt Env Files

Statt eigene `.env` Files für jede Stage zu pflegen: 
```bash
# Shell Startup
export KI_STAGE=prod
export KI_CFG_LLM__PROVIDERS__KI__BASE_URL=https://ki.company.com
export KI_CFG_KNOWLEDGE__DATA_ROOT=/var/lib/ki/data
```

Das ist höhere Priorität als Stages und ist einfacher zu debuggen.

### 3. Secrets IMMER in creds.yaml

❌ **FALSCH**:
```yaml
# stage.yaml
llm:
  providers:
    ki:
      api_key: "secret123"  # NIEMALS!
```

✅ **RICHTIG**:
```yaml
# creds.yaml (nur diese Datei in .gitignore!)
llm:
  providers:
    ki:
      api_key: "secret123"

# stage.yaml
llm:
  provider: ki
```

creds.yaml wird am Ende deep-merged und ist damit die höchste Priorität (nach Env-Vars).

## How kicli-code-assist Should Use This Pattern

### Prerequisites

1. **Struktur**: `config/stages/`, `config/profiles/`, `config/defaults/`, `config/runtime/`
2. **Files**: 
   - `ki.yaml` (main config mit ausführlicher Dokumentation)
   - `creds.yaml` (.gitignored, secrets nur hier)
   - `schema/kicli-code-assist.schema.yaml` (app-spezifisches schema)

### Stage Definitions

Für kicli-code-assist könnten die Stages sein:

| Stage | Nutzung |
|-------|---------|
| dev-lokal | Lokal dev, alle services up (Ollama, K8s optional) |
| dev-compose | Local Docker Compose, K8s disabled |
| ci-test | GitHub Actions Test Environment |
| prod | Production Deployment |

### Implementation Steps

1. **Create stage files** in `config/stages/`
   ```bash
   touch config/stages/{dev-lokal,dev-compose,ci-test,prod}.yaml
   ```

2. **Load config exactly like ki-knowledge**:
   ```python
   from ki_core.config import load_config, active_layers
   
   layers = active_layers()  # {"stage": "dev-lokal", "profile": None}
   config = load_config()    # Fully resolved config dict
   ```

3. **Use ConfigManager for LLM provider**:
   ```python
   from ki_core.config import ConfigManager
   
   cm = ConfigManager()
   provider = cm.get_llm_provider()  # Intelligente Detection
   ```

## Testing Config Changes

### Interactive Testing

```bash
# Test dev-lokal
export KI_STAGE=dev-lokal
python -c "from ki_core.config import load_config; c = load_config(); print(c.get_path('llm.provider'))"

# Test prod
export KI_STAGE=prod
python -c "from ki_core.config import load_config; c = load_config(); print(c.get_path('llm.provider'))"
```

### Validation

```bash
# Validate against schema
export KI_STAGE=dev-lokal
stackctl -t local normalize  # merges config and validates
```

## Common Mistakes

1. **Nicht `.active_stage` Marker verwenden**: Immer env var `KI_STAGE` setzen, nicht Marker-Datei.
   - Marker ist nur Fallback für CI/CD pipelines

2. **Stage-Datei zu groß**: Sollte nur Unterschiede haben, nicht alles duplizieren

3. **Secrets in Stage-Datei**: Nutze creds.yaml stattdessen

4. **LLM Provider-Detection ignorieren**: `get_llm_provider()` kann anderes zurück geben als `llm.provider` - das ist Feature, nicht Bug

5. **Env-Var Naming falsch**: `KI_CFG_LLM__PROVIDERS__KI__BASE_URL` mit `__` für nesting, nicht `.`

## Debugging Config Resolution

```bash
# Vollständige Merge-Trace sehen
export KI_STAGE=dev-lokal
python -c "
from ki_core.config import load_config, active_layers
import json

layers = active_layers()
config = load_config()

print('Active layers:', layers)
print('Full config llm section:', json.dumps(config.get('llm', {}), indent=2))
"
```

## Schema Integration

Alle Stages müssen gegen vereinigtes Schema validiert werden:

```
ki-core base schema
    + 
ki-knowledge app schema
    + 
kicli-code-assist app schema
    = 
Validiertes, merged Schema
```

Die ki-core Config-Loader findet automatisch alle `.schema.yaml` Dateien.

## References

- **Implementation**: `/home/flow/dev_flow/ki-core/src/ki_core/config.py`
- **Schema Utilities**: `/home/flow/dev_flow/yaml_cfg_wizard/src/yaml_cfg_wizard/core.py`
- **ki-knowledge Real Examples**: `/home/flow/dev_flow/ki-knowledge/config/stages/*.yaml`
