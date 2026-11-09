---
project: ki-knowledge
agent_project: ki-knowledge
scope: archive
created: null
updated: "2026-11-08 01"
update_reason: "Überholte Aussagen zur Provider-Auswahl archiviert"
status: archived
semantic_blocks:
  - old-assumption
  - boundary
relations:
  - target: README.md
    type: parent
    reason: "Deploymentarchiv"
  - target: ../CONFIG_MERGE_REFERENCE.md
    type: reference
    reason: "Ursprung der früheren Provider-Beschreibung"
  - target: ../REFERENCE_FOR_KICLI_ASSIST.md
    type: reference
    reason: "Weitere frühere Provider-Beschreibung"
---

# Früheres Provider-Konzept

<a id="old-assumption"></a>
## Frühere Annahme [old-assumption]

In älteren Deploymentunterlagen wurde behauptet, die Anwendung könne trotz
explizit konfiguriertem `ollama` wegen eines vorhandenen OpenAI-Schlüssels
automatisch `openai` auswählen. Ein Pseudocode dazu nannte eine Prüfung auf
einen expliziten Provider und anschließend eine Prioritätsliste für OpenAI,
Ollama, KI und Mock. Die pauschale Behauptung widersprach bereits dieser
Prüfung auf explizite Auswahl.

Der frühere Pseudocode:

```text
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

<a id="boundary"></a>
## Heutige Abgrenzung [boundary]

Die Projektintegration adaptiert ihre Konfiguration über
`ki_knowledge.llm_provider` an `ki_core.chat`. Ein expliziter Provider bleibt
maßgeblich; automatische Erkennung wird für `auto` bei Client-Erzeugung
aufgelöst. Die bloße Anzeige von Einstellungen fragt Dienste nicht dafür ab.
Ein Fehler eines expliziten Providers löst keinen stillen Providerwechsel aus.

Die genaue gemeinsame Implementierung und ihre jeweils aktuelle
Auto-Erkennung gehören zu ki-core, nicht als zweite Kopie in dieses Projekt.
