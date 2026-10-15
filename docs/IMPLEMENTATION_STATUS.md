# CLI Architecture - Implementation Status & Next Steps

**Last Updated:** Phase 2 (In Progress)

---

## Current Architecture State

The KI ecosystem is transitioning from isolated CLI implementations to a shared base architecture:

```
yi-core (Orchestrator)
  └─ ki_core.commands.* (doctor, config, profile, stage, ...)
  
Consuming Apps:
  ├─ kicli-assist (✅ Phase 2 delegating)
  ├─ ki-chat (✅ Phase 2 base impl)
  ├─ yaml-cfg (planned: Phase 2b delegation)
  ├─ ki-knowledge (planned: Phase 2c adoption)
  └─ ia3simworld (planned: future integration)
```

---

## What to Do in Each Project

### kicli-code-assist ✅ DONE

**Status:** Phase 2 implementation complete

**What was done:**
- Added delegating functions: `run_config()`, `run_profile()`, `run_stage()`
- Updated `cli_commands.yaml` with new command groups
- All config/profile/stage commands now available via kicli-assist CLI

**Available commands:**
```bash
kicli-assist doctor                  # Config diagnostics
kicli-assist -q doctor               # Quiet mode (no config path output)

kicli-assist config resolve          # Full config resolution
kicli-assist config verify           # Schema validation
kicli-assist config skeleton -o cfg.yaml
kicli-assist config show [key]       # Show specific keys

kicli-assist profile list            # List profiles
kicli-assist profile set <name>      # Activate profile
kicli-assist profile active          # Show active

kicli-assist stage list              # List stages
kicli-assist stage set <name>        # Activate stage
kicli-assist stage active            # Show active
```

**Note:** The `-q/--quiet` flag at the top level suppresses config file location output on all subcommands.

---

### yaml-cfg-wizard ⏳ PLANNED (Phase 2b)

**Current state:** Independent YAML tool with own CLI (Typer-based)

**Options going forward:**

**Option A: Stay independent (recommended for now)**
- Keep yaml-cfg as standalone tool
- No dependency on ki-core
- Users can use either:
  - `yaml-cfg config resolve ...` (direct)
  - `kicli-assist config resolve ...` (via ki-core wrapper)

**Option B: Delegate to ki-core (future)**
- Add thin wrapper layer that delegates to ki_core.commands.config
- Still no dependency on ki-core at library level
- CLI could offer both interfaces for backward compatibility

**Action needed:**
1. Document in yaml-cfg's README that config commands are also available via kicli-assist
2. Reference CLI_ARCHITECTURE_ROADMAP.md in docs
3. If choosing Option B later: create delegation layer

---

### ki-knowledge ⏳ PLANNED (Phase 2c)

**Current state:** Unknown CLI structure

**What to do:**
1. Read CLI_ARCHITECTURE_ROADMAP.md
2. If you have a Python CLI:
   - Import from `ki_core.commands` 
   - Delegate config/profile/stage to ki-core
   - Example: see kicli-assist's run_config() wrapper
3. If you have non-Python CLI (Django admin, Go binary, etc.):
   - Consider adding thin Python wrapper for config commands
   - Or document how to call ki-core commands from your app

**Recommended commands to support:**
```bash
ki-knowledge doctor                 # (delegate to ki-core)
ki-knowledge config resolve         # (delegate to ki-core)
ki-knowledge profile list           # (delegate to ki-core)
```

---

### ia3simworld ⏳ PLANNED (Future)

**Current state:** Multi-service architecture (Go simulator + Python agents + web frontend)

**What to do:**
1. Review CLI_ARCHITECTURE_ROADMAP.md
2. If adding/maintaining CLI commands:
   - Avoid duplicating config management
   - Delegate to ki-core commands where possible
   - Example: Python launcher script could wrap ki-core
3. If no Python CLI yet: consider minimal wrapper for config diagnostics

---

## Implementation Checklist

### For Apps Adopting Phase 2

- [ ] Read CLI_ARCHITECTURE_ROADMAP.md 
- [ ] Check if your CLI is Python (Typer, Click, raw argv, etc.)
- [ ] If yes: create delegation functions like `run_config()`, `run_profile()`, etc.
- [ ] Update your command definitions (YAML, Click groups, etc.)
- [ ] Add command examples to your README
- [ ] Test all config/profile/stage commands work
- [ ] Commit changes with reference to Phase 2
- [ ] Update README with link to CLI_ARCHITECTURE_ROADMAP.md

### For Dependency Maintainers

- [ ] Ensure ki-core.commands are exported in `__init__.py`
- [ ] Maintain `echo_fn` parameter pattern for CLI-agnosticism
- [ ] Test that both `ki-chat config resolve` and `kicli-assist config resolve` work
- [ ] Document any new commands in roadmap
- [ ] Coordinate breaking changes with downstream apps

---

## Testing Phase 2

```bash
# Test ki-core base CLI
ki-chat config resolve              # Should show full config
ki-chat profile list                # Should list profiles
ki-chat doctor                       # Should show config chain

# Test app-specific wrapper
kicli-assist config resolve         # Should show same output
kicli-assist -q config resolve      # Quiet mode working
kicli-assist profile set dev        # Should activate profile
kicli-assist profile active         # Should show active

# Test cross-compatibility
# Both should show same results:
kicli-assist doctor
ki-chat doctor
```

---

## Known Limitations / Assumptions

1. **Profile/Stage markers:** Currently use `.active_profile` and `.active_stage` files
   - These are text files in `config/profiles/` and `config/stages/` dirs
   - Future: May move to centralized marker location

2. **Config resolution:** Relies on 8-layer resolution chain from YAML_CONFIG_SYSADMIN.md
   - Order: creds.yaml → env vars → runtime.yaml → stage → profile → ki.yaml → defaults → schema defaults

3. **CLI framework compatibility:** 
   - Tested: Click (kicli-assist), raw argv (ki-chat)
   - Planned: Typer (yaml-cfg), Django admin (ki-knowledge)

4. **yaml-cfg independence:** 
   - yaml-cfg has NO dependency on ki-core
   - ki-core imports yaml-cfg for ConfigResolver
   - This direction is intentional and must be maintained

---

## References

- **CLI_ARCHITECTURE_ROADMAP.md** - This directory, full technical roadmap
- **YAML_CONFIG_SYSADMIN.md** - This directory, config resolution details
- **ki-core/src/ki_core/commands/** - Shared implementations
- **kicli-code-assist/kicli_code_assist/cli.py** - Example delegation pattern

---

## Questions / Issues?

When in doubt:
1. Check if it's a shared config command → should live in ki_core.commands
2. Check if it's app-specific → should live in app's cli.py
3. Check the dependency direction → Apps → ki-core → yaml-cfg (NEVER reverse)
4. Look at kicli-assist as reference implementation
