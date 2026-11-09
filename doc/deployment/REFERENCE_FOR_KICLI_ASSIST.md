---
project: ki-knowledge
agent_project: ki-knowledge
scope: deployment
created: "2026-10-31 03"
updated: "2026-11-08 01"
update_reason: "Falsche normalize- und Provider-Empfehlungen archiviert"
status: draft
---

# Ki-Knowledge as Reference for kicli-code-assist

> **Warnung:** Diese projektübergreifende Referenz muss insgesamt noch auf
> Aktualität und Zuständigkeit geprüft werden. Die
> [Fehlannahmen zu normalize](archiv/NORMALIZE_FEHLANNAHMEN.md) sind archiviert.

**Date**: 2026-10-31
**Purpose**: kicli-code-assist team should use this reference when implementing their own deployment infrastructure.

## What We Learned (Task Summary)

### 1. Stage Configuration ✅

ki-knowledge has 4 well-defined stages:

```
dev-lokal  → Docker Compose on host, Ollama local, debug=true
dev-mk     → Minikube K8s, in-cluster Ollama, debug=false
prod-k8s   → Production K8s, Company KI provider
prod       → Ubuntu host, Docker Compose + Systemd, Company KI
```

**Key finding**: Only ONE stage is active at a time. Selection via:
- Environment variable: `export KI_STAGE=dev-lokal`
- Marker file: `config/stages/.active_stage`

### 2. Config-Merge Semantics ✅

The config resolution pipeline has 8 layers (highest to lowest priority):

```
1. creds.yaml              (secrets)
2. Env vars                (KI_CFG_* prefix)
3. Runtime config          (config/runtime/runtime.yaml)
4. ACTIVE STAGE            (ONE file only)
5. ACTIVE PROFILE          (ONE file only)
6. Main config             (ki.yaml)
7. Defaults                (config/defaults/*.yaml)
8. Schema defaults         (from .schema.yaml files)
```

**Critical insight**: `deep_merge()` is RECURSIVE for dicts but OVERWRITES non-dict values.

```python
# This means stage files should be MINIMAL - only override what's different!
```

### 3. Provider Detection

Die frühere [Annahme eines automatischen Wechsels trotz expliziter Auswahl](archiv/PROVIDER_DETECTION_ALTKONZEPT.md)
ist archiviert. Provider-Auswahl und Client-Erzeugung liegen in `ki_core.chat`;
die konkrete Integration des Schwesterprojekts ist dort gesondert zu prüfen.

### 4. CI/CD Testing ✅

Created `.github/workflows/test.yml` that validates:
- All stages load correctly
- Merge order (stage overrides base)
- Env var override precedence
- LLM provider detection
- No secrets in config files
- Schema validation

### 5. Documentation ✅

Created 4 documentation files in `doc/deployment/`:

| File | Purpose |
|------|---------|
| **README.md** | Architecture overview, quick start |
| **CONFIG_MERGE_REFERENCE.md** | Deep dive on merge semantics, best practices |
| **STAGES.md** | Detailed guide for each stage (setup, monitoring, troubleshooting) |
| **TESTING.md** | Config validation, health checks, CI/CD template |

## For kicli-code-assist Implementation

### Directory Structure to Use

```
kicli-code-assist/
├── ki.yaml                              # Main config
├── creds.yaml                           # Secrets (.gitignored)
├── config/
│   ├── stages/
│   │   ├── dev-lokal.yaml               # Docker on host
│   │   ├── dev-compose.yaml             # Optional: Local compose
│   │   ├── ci-test.yaml                 # For GitHub Actions
│   │   └── prod.yaml                    # Production
│   ├── profiles/                        # Optional
│   ├── defaults/                        # Optional
│   └── runtime/                         # Optional, host-local
├── schema/
│   └── kicli-code-assist.schema.yaml    # App-specific schema
└── .github/workflows/
    └── test.yml                         # Use ki-knowledge template!
```

### Load Config in Python

```python
from ki_core.config import load_config, ConfigManager

# Method 1: Get full resolved config
config = load_config()
provider = config.get_path("llm.provider")  # May be "auto" or explicit

# Method 2: Use ConfigManager for convenience
cm = ConfigManager()
provider = cm.get_llm_provider()  # Intelligent detection
logging = cm.get_logging_config()
```

### Stage Files Should Be Minimal

❌ **DON'T**:
```yaml
# config/stages/dev-lokal.yaml (WRONG - too much!)
llm:
  provider: ollama
  providers:
    ollama:
      base_url: http://localhost:11434
      model: llama3.2
apps:
  kicli:
    server:
      port: 8000
      debug: true
```

✅ **DO**:
```yaml
# config/stages/dev-lokal.yaml (CORRECT - minimal)
llm:
  provider: ollama
apps:
  kicli:
    server:
      debug: true
```

**Why**: Everything else merges from ki.yaml + defaults + creds.yaml.

### Environment Variable Format

```bash
# ✓ Correct: use __ for nesting
export KI_CFG_LLM__PROVIDERS__KI__API_KEY=secret123
export KI_CFG_APPS__KICLI__SERVER__PORT=8001

# ✗ Wrong: don't use . for nesting in env vars
export KI_CFG_llm.providers.ki.api_key=secret123  # Wrong!
```

### Secrets Management

```yaml
# ✓ CORRECT - creds.yaml (add to .gitignore!)
llm:
  providers:
    ki:
      api_key: "real-secret-key"

# ✗ WRONG - never in config files
apps:
  kicli:
    api_key: "real-secret-key"  # DON'T!
```

### CI/CD Testing Template

```yaml
# .github/workflows/test.yml
# Copy structure from ki-knowledge/.github/workflows/test.yml
# Adapt app/stage names for kicli-code-assist

jobs:
  config-validation:
    steps:
      - Test all stages load
      - Validate merge order
      - Test env var override
      - Test provider detection
      - Check for secrets
```

## Copy-Paste Resources

### 1. Config Merge Test

```bash
python << 'PYTHON'
import os
import sys
sys.path.insert(0, '../ki-core/src')

os.environ['KI_STAGE'] = 'dev-lokal'

from ki_core.config import load_config, ConfigManager

config = load_config()
cm = ConfigManager()

print(f"Stage: {os.getenv('KI_STAGE')}")
print(f"Config provider: {config.get_path('llm.provider')}")
print(f"Detected provider: {cm.get_llm_provider()}")
PYTHON
```

### 2. Health Check Script

```python
# scripts/health_check.py
from ki_core.config import load_config, ConfigManager

def check_config():
    try:
        config = load_config()
        cm = ConfigManager()
        provider = cm.get_llm_provider()
        print(f"✓ Config OK (provider: {provider})")
        return True
    except Exception as e:
        print(f"✗ Config failed: {e}")
        return False
```

### 3. Stack Control Commands

```bash
# Set stage for this session
export KI_STAGE=dev-lokal

# Start all services
stackctl -t local start

# Check status
stackctl -t local status

# Stop all services
stackctl -t local stop

# View logs
stackctl -t local logs <service>
```

## Testing Your Implementation

### Before Deploying

```bash
# 1. Verify all stages load
for stage in dev-lokal dev-compose ci-test prod; do
    export KI_STAGE=$stage
    python -c "from ki_core.config import load_config; load_config(); print('✓ $stage')"
done

# 3. Run health checks
python scripts/health_check.py

# 4. Start stack and test
stackctl -t local start
sleep 5
curl http://127.0.0.1:8000/  # or your app port
stackctl -t local stop
```

## Common Mistakes to Avoid

| Mistake | Impact | Fix |
|---------|--------|-----|
| Stage file too big (duplicates ki.yaml) | Hard to maintain, easy to miss overrides | Keep stage files minimal, only override differences |
| Secrets in config files | Security leak, can be committed | Put secrets ONLY in creds.yaml (.gitignored) |
| Using marker file instead of env var | Inflexible for CI/CD | Always use `export KI_STAGE=...` |
| Expecting all stages active | Only one is active! | Set `KI_STAGE` env var correctly |
| Assuming an explicit provider can silently change | Misleading provider expectations | Check the project's integration and `ki_core.chat` |
| Wrong env var nesting (use . not __) | Env var not recognized | Use `KI_CFG_LLM__PROVIDERS__KI__API_KEY` with __ |
| Not validating in CI/CD | Config errors caught late | Use ki-knowledge test.yml as template |

## FAQ

**Q: Can I have profiles in addition to stages?**
A: Yes! Profiles work the same way as stages. One stage + one optional profile can be active. Use case: stage=prod, profile=high-volume vs profile=low-power.

**Q: What if I need host-specific config that shouldn't be committed?**
A: Use `config/runtime/runtime.yaml` or environment variables. These override stages.

**Q: Should ki.yaml have production-like values or minimal placeholders?**
A: Minimal placeholders. ki.yaml is the base for ALL stages. Production-specific values go in `config/stages/prod.yaml`.

**Q: How do I know if my config is valid?**
A: Consult the current ki-core and yaml-cfg-wizard documentation for the
appropriate validation method. `stackctl normalize` is not a read-only check.

**Q: Can my app use different stages per module?**
A: No, only one global stage. If you need per-module config, use profiles or nested YAML keys.

## References

- **ki-knowledge deployment docs**: `/home/flow/dev_flow/ki-knowledge/doc/deployment/`
- **ki-core config implementation**: `/home/flow/dev_flow/ki-core/src/ki_core/config.py`
- **yaml-cfg-wizard merge logic**: `/home/flow/dev_flow/yaml_cfg_wizard/src/yaml_cfg_wizard/core.py`
- **Real ki-knowledge stages**: `/home/flow/dev_flow/ki-knowledge/config/stages/`

## Next Steps

1. **Copy** `.github/workflows/test.yml` from ki-knowledge
2. **Create** `config/stages/` directory
3. **Write** minimal stage files (just the overrides)
4. **Setup** creds.yaml (.gitignored) for secrets
5. **Test** with `KI_STAGE=dev-lokal` env var
6. **Validate** using the current config tooling and its documentation
7. **Integrate** config loading in your app

---

This document is the bridge between ki-knowledge's proven implementation and kicli-code-assist's needs. It's complete and ready to use.
