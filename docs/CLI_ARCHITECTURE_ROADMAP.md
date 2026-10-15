# CLI Architecture Roadmap

**Status:** Phase 2 (🔄 In Progress)  
**Goal:** Eliminate CLI duplication across all projects

---

## Problem

Current state (chaos):
```
yaml-cfg (Typer)          → config resolve/verify/skeleton
ki-chat (raw sys.argv)    → mock/ollama/openai chat, cert-diagnose
kicli-assist (Click)      → tui/tmux/chat/openinterpreter, doctor
ki-knowledge (?)          → Django admin + config
ia3simworld (?)           → Go services + launcher
```

**Issues:**
- No shared base → each app reinvents CLI
- `doctor` command only in kicli-assist (specific, not general)
- `config-skeleton` duplicated in ki-chat + yaml-cfg
- Inconsistent technologies (Typer, Click, raw argv)
- Apps can't easily share config management commands

---

## Vision: Hierarchical CLIs

```
┌─────────────────────────────────────────────────────┐
│  ki-core base (Typer + Click)                       │
│  ├─ config resolve/skeleton/verify/doctor/show      │
│  ├─ profile list/set/active                         │
│  ├─ stage list/set/active                           │
│  ├─ cert-diagnose                                   │
│  └─ (future: secret management)                     │
└─────────────────────────────────────────────────────┘
        ▲               ▲               ▲
        │               │               │
    ┌───┴───┐       ┌───┴─────┐    ┌──┴────┐
    │ki-chat│       │kicli-   │    │ki-    │
    │       │       │assist   │    │know   │
    │(Typer)│       │(Click)  │    │ledge  │
    │ - chat│       │ - tui   │    │(TBD)  │
    │       │       │ - tmux  │    │       │
    └───────┘       │ - openai│    └───────┘
                    │ - chat  │
                    └─────────┘
```

Each app:
- Imports `ki_core.commands.*` (shared)
- Adds own subcommands via Typer/Click groups
- Both `ki-core doctor` and `kicli-assist doctor` work

---

## Phase 1: Centralize "doctor" (✅ COMPLETE)

**Done:**
- ✅ `ki_core/commands/doctor.py` - shared base implementation
- ✅ `ki-chat doctor` calls shared version
- ✅ `kicli-assist doctor` delegates to ki-core

**Impact:** Any app now gets config diagnostics for free

**Test:**
```bash
# Both work, both show same chain:
ki-chat doctor
kicli-assist doctor
```

---

## Phase 2: Centralize config/profile/stage (🔄 IN PROGRESS)

Move from `yaml-cfg config resolve ...` to:
```bash
# Unified across all apps:
ki-chat config resolve ...          # via ki-core CLI (✅ DONE)
kicli-assist config resolve ...     # via app wrapper (✅ DONE)
ki-knowledge config resolve ...     # (planned)
```

**Completed:**
- ✅ `ki_core/commands/config.py` - resolve, verify, skeleton, show
- ✅ `ki_core/commands/profile.py` - list, set, active
- ✅ `ki_core/commands/stage.py` - list, set, active
- ✅ `ki_core/cli.py` updated with config/profile/stage commands
- ✅ `kicli-assist cli.py` delegates config/profile/stage to ki-core
- ✅ `kicli-assist cli_commands.yaml` includes config/profile/stage groups

**Remaining (Phase 2b-c):**
- Update yaml-cfg to use ki_core.commands (optional: keep as thin wrapper)
- Update ki-knowledge team on roadmap
- Update ia3simworld team on roadmap
- Propagate documentation to all projects

**Implementation pattern verified:**
```python
# Base implementation in ki_core/commands/
def run_config(echo_fn=None, subcommand="resolve", **kwargs):
    if echo_fn is None:
        echo_fn = print
    # wrapped logic here
    
# App wrapper
def run_config(**kwargs):
    from ki_core.commands import run_config as base_config
    base_config(echo_fn=click.echo, **kwargs)
```

**Test:**
```bash
ki-chat config resolve              # Shows full resolved config
kicli-assist config resolve -q      # Quiet mode works
kicli-assist profile list            # Profile management
kicli-assist stage set dev           # Stage management
```

---

## Phase 3: Single "ki" CLI with app namespaces (Future)

Optional long-term unification:
```bash
ki doctor                 # Base config diagnostics
ki config resolve ...     # Base config management
ki profile list           # Base layer management

ki assist doctor          # Equivalent to kicli-assist doctor
ki assist tui             # Equivalent to kicli-assist tui

ki knowledge config ...   # Equivalent to future ki-knowledge tool
```

---

## Implementation Guidelines

### For new commands in ki-core:

```python
# ki_core/commands/my_feature.py
def run_my_feature(echo_fn=None, **kwargs):
    """Shared implementation, CLI-agnostic."""
    if echo_fn is None:
        echo_fn = print
    echo_fn("output")

# ki_core/commands/__init__.py
from ki_core.commands.my_feature import run_my_feature
__all__ = ["run_my_feature"]
```

### For app-specific CLIs:

```python
# kicli_code_assist/cli.py
from ki_core.commands import run_my_feature as ki_base_my_feature

def run_my_feature() -> None:
    """App-specific wrapper (if needed)."""
    ki_base_my_feature(echo_fn=click.echo)
```

### Dependency direction (always):
```
Apps → ki-core/commands  (import)
ki-core/commands → config APIs (import)
NEVER: ki-core/commands → app code
```

---

## Next Steps

1. **Phase 2a (next):** Create `ki_core/commands/config.py` with resolve/verify/skeleton
2. **Phase 2b:** Update `yaml-cfg` to use it (or make yaml-cfg a wrapper)
3. **Phase 2c:** Have kicli-assist delegate `config *` to ki-core
4. **Phase 3:** Coordinate with ki-knowledge and ia3simworld teams

---

## Checklist: Adding New Shared Command

- [ ] Create `ki_core/commands/my_cmd.py` with `run_my_cmd(echo_fn=print, ...)`
- [ ] Export from `ki_core/commands/__init__.py`
- [ ] Add to `ki_core/cli.py` for `ki-chat my-cmd` support
- [ ] Each downstream app creates wrapper in their `cli.py`
- [ ] Test both base and app versions work
- [ ] Document in this roadmap

---

## References

- YAML_CONFIG_SYSADMIN.md - Config resolution order  
- ki_core/commands/ - Shared implementations
- Each app's cli.py - Delegation patterns

## Dependency Architecture

```
yaml-cfg (independent generic YAML tool)
  ├─ Library: ConfigResolver, merge_schemas, scaffold_skeleton
  └─ CLI: config resolve/skeleton/verify, profile, stage
  └─ NO dependency on ki-core
  
          ↓ (ki-core imports yaml-cfg)
          
ki-core (orchestrator for all KI apps)
  ├─ Library: load_config(), active_layers(), LLM clients
  ├─ Commands: doctor (✅), config (Phase 2), profile (Phase 2), stage (Phase 2)
  │   └─ These wrap yaml-cfg library components
  └─ CLI: ki-chat (delegates to commands)

          ↓ (apps import ki-core)
          
App CLIs (kicli-assist, ki-knowledge, ia3simworld, ...)
  ├─ App-specific: tui, tmux, chat, web-ui, simulator, etc.
  └─ Shared config: all delegate to ki_core.commands
  
Why this direction:
  • yaml-cfg can be used independently
  • ki-core orchestrates for KI specifically
  • Apps don't reinvent the wheel
  • Clear single source of truth per layer
