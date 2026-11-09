---
project: ki-knowledge
agent_project: ki-knowledge
scope: features
created: "2026-09-02 18"
updated: "2026-11-08 03"
update_reason: "Historische Output-Anforderungen semantisch gegliedert"
status: draft
semantic_blocks:
  - vision
  - historical-scope
  - historical-exclusions
  - configuration
  - source-requirements
  - content-generation
  - versioning
  - quality
  - architecture-sketch
  - implementation-questions
  - roadmap
  - acceptance-criteria
  - references
relations:
  - target: ../architecture/KI-KNOWLEDGE-KONZEPT.md
    type: reference
    reason: "Neues fachliches Zielbild und offene Ausgabeplanung"
---

# Knowledge Presentation Feature – Anforderungen

> **Historischer Anforderungsentwurf, nicht aktueller Produkt-Scope:** Die
> folgenden Abschnitte beschreiben einen 2026 vorgeschlagenen Markdown-Output.
> Insbesondere der Ausschluss von Wissensblöcken in Abschnitt 3 ist keine
> Vorgabe für die [neue Ausgabeplanung](../architecture/KI-KNOWLEDGE-KONZEPT.md#discovery-and-output).
> Format, Struktur, Freigabe und Implementierungsstand sind gesondert zu
> prüfen; mögliche weiterhin nützliche Anforderungen bleiben erhalten.

**Agentenbearbeitung, 2026-11-08:** Die Abschnitts-IDs strukturieren den
historischen Entwurf; sie bestätigen weder die Anforderungen noch den
Implementierungsstand. Eine fachliche Übernahme erfordert Prüfung.

**Arbeitstitel:** Knowledge Presentation (Wissenspräsentation)  
**Status:** Anforderungsphase (Phase 1)  
**Datum:** 2026-09-02

---

<a id="1-zielbild"></a>
<a id="vision"></a>
## 1. Zielbild [vision]

Eine **browsbare Wissens-Website als Markdown-Quellbestand** erzeugen, die später mit einem Static Site Generator (SSG) gebaut und aktualisiert werden kann.

Im ersten Schritt geht es **nur um Inhalte und Dateistruktur**, nicht um semantische Anbindung oder Knowledge-Block-Integration.

---

<a id="2-scope-phase-1"></a>
<a id="historical-scope"></a>
## 2. Scope (Phase 1) [historical-scope]

1. Ausgabe als Markdown-Dateien inkl. sinnvoller Ordnerstruktur.
2. Navigierbare Struktur über Seitenhierarchie und interne Links.
3. Nutzung vorhandener Quelldokumente als inhaltliche Basis.
4. Versionierbare „Originalversion" als Startstand.
5. Vorbereitung auf KI-gestützte, halbautomatische Weiterentwicklung/Versionierung.

---

<a id="3-nicht-im-scope-jetzt-explizit-ausgeschlossen"></a>
<a id="historical-exclusions"></a>
## 3. Nicht im Scope (jetzt explizit ausgeschlossen) [historical-exclusions]

**Überholt als allgemeine Produktgrenze:** Der folgende Ausschluss gilt nur
für den damaligen Entwurf, nicht für das neue Wissensmodell.

1. Keine semantische Technologie-Integration.
2. Keine Knowledge-Blocks-Anbindung.
3. Kein finales SSG-Setup/Theme/Build-Pipeline-Zwang (nur SSG-kompatibler Content-Output).

---

<a id="4-konfiguration"></a>
<a id="configuration"></a>
## 4. Konfiguration [configuration]

### 4.1 Config-Eintrag

Neuer Config-Eintrag für den Arbeitstitel der Präsentation und Ausgabeziel.

**Kandidat:** `knowledge_presentation_title` im ki-core Config-System

### 4.2 Default-Ausgabepfad

```
<data_root>/<domain>/output/<working_title>
```

**Komponenten:**
- `data_root`: aus vereinheitlichtem `ki-core` Config-System
- `domain`: aus aktiver/übergebener Domäne  
- `working_title`: konfigurierbar (Arbeitstitel der Wissenspräsentation)

---

<a id="5-input-quellenanforderungen"></a>
<a id="source-requirements"></a>
## 5. Input-/Quellenanforderungen [source-requirements]

1. Es gibt definierte Quelldokumente als Referenzbasis für den ersten Entwurf.
2. Inhalte sollen **sinngemäß möglichst vollständig** übernommen werden.
3. Der erste ausgeleitete Stand wird als **Originalversion** festgehalten.
4. Quelldokumente können aus verschiedenen Quellen stammen:
   - Markdown-Blöcke (Wissensbase)
   - Externe Dokumente/URLs
   - Importierte Inhalte (z. B. aus älteren Quellen)

---

<a id="6-content-generierung-phase-1-verhalten"></a>
<a id="content-generation"></a>
## 6. Content-Generierung (Phase 1 Verhalten) [content-generation]

1. Erzeuge Startseite und thematische Unterseiten als Markdown.
2. Lege eine klare Informationsarchitektur fest:
   - Kapitel/Themen/Unterthemen
   - Sinnvolle Hierarchie-Tiefe
3. Erzeuge interne Verlinkung für Browsing.
4. Schreibe reproduzierbar in den konfigurierten Zielordner.
5. Überschreibe nicht unkontrolliert; Versionierung muss nachvollziehbar sein.

---

<a id="7-versionierung--evolvierbarkeit"></a>
<a id="versioning"></a>
## 7. Versionierung & Evolvierbarkeit [versioning]

1. Originalversion wird als baseline versioniert (z. B. `v1-original`).
2. Spätere KI-unterstützte Überarbeitungen bauen darauf auf.
3. Änderungen sollen halbautomatisch erzeugbar und versionierbar sein.
4. Markdown-Struktur muss diff-freundlich sein (saubere Diffs über Versionen).
5. Metadaten/Frontmatter können zur Versionsverfolgung genutzt werden.

---

<a id="8-qualitätsanforderungen"></a>
<a id="quality"></a>
## 8. Qualitätsanforderungen [quality]

1. **Markdown-Format:** SSG-freundlich
   - Saubere ATX-Überschriften (#, ##, ###, …)
   - Interne Links in standardisiertem Format
   - Optional: YAML Frontmatter für Metadaten
   - Konsistente Zeilenumbrüche und Absätze

2. **Dateibenennung:** Konsistent und URL-freundlich
   - Slugging: `lowercase-with-hyphens`
   - Reproduzierbar
   - Aussagekräftig

3. **Verlinkungs-Konsistenz:**
   - Interne Links verwenden relative Pfade
   - Automatische Generierung von Navigationsmenüs
   - Vermeidung von broken links

4. **Deterministische Ausgabe:**
   - Bei gleichem Input und Config → gleicher Output
   - Reproduzierbar für CI/CD-Integration

---

<a id="9-architektur-skizze"></a>
<a id="architecture-sketch"></a>
## 9. Architektur-Skizze [architecture-sketch]

```
<domain>/output/<working_title>/
├── index.md                    # Startseite
├── overview.md                 # Übersichtsseite
├── topics/
│   ├── topic-1/
│   │   ├── index.md           # Thema-Übersicht
│   │   ├── subtopic-a.md      # Unterthema
│   │   └── subtopic-b.md
│   └── topic-2/
│       └── index.md
├── metadata.yml               # Versionierung, Quellenangaben
└── _originals/               # Originalversion-Archiv
    └── v1-original/
        ├── (wie oben)
        └── metadata.yml
```

---

<a id="10-offene-punkte-für-die-umsetzung"></a>
<a id="implementation-questions"></a>
## 10. Offene Punkte für die Umsetzung [implementation-questions]

1. **Config-Key-Benennung:**
   - Vorschlag: `knowledge_presentation_title` in ki-core
   - Alternative: `knowledge_presentation_config` (Objekt mit Titeln, Domains, etc.)

2. **Quelldokumente:**
   - Konkreter Katalog, welche Quelldokumente initial gelten
   - Mapping: Quelle → Kapitel/Thema

3. **Minimales Seiten-Schema:**
   - Pflicht-Seiten: `index.md`, `overview.md`
   - Standard-Themen-Struktur definieren
   - Template-Vorgaben für Markdown-Struktur

4. **Versionsschema:**
   - Benennung der Originalversion (z. B. `v1-original`, `baseline-{timestamp}`)
   - Incrementing für KI-überarbeitete Versionen (z. B. `v1-ai-enhanced`)

5. **Frontmatter-Schema:**
   - Minimale Metadaten: Titel, Datum, Quelle, Version
   - Optional: Tags, Status, Review-Info

6. **KI-Integration (späte Phase):**
   - Schnittstelle für halbautomatische Überarbeitungen
   - Diff-basierte Anwendung von Änderungen
   - Audit-Trail für KI-Eingriffe

---

<a id="11-implementation-roadmap-phaseneinteilung"></a>
<a id="roadmap"></a>
## 11. Implementation-Roadmap (Phaseneinteilung) [roadmap]

### Phase 1: Grundgerüst
- [ ] Config-Eintrag hinzufügen
- [ ] Ausgabeverzeichnis-Logik implementieren
- [ ] Basis-Dateistruktur erzeugen
- [ ] Quelldokumentation laden und übernehmen
- [ ] Originalversion als Baseline speichern

### Phase 2: Navigation & Struktur
- [ ] Interne Link-Generierung
- [ ] Navigationsmenü (automatisch aus Hierarchie)
- [ ] Seiten-Template-System
- [ ] Metadata-Handling

### Phase 3: Versionierung
- [ ] Versionierungs-Workflow
- [ ] Diff-freundliche Speicherung
- [ ] Versions-Vergleich

### Phase 4: KI-Integration (künftig)
- [ ] KI-unterstützte Überarbeitungen
- [ ] Halbautomatische Änderungsanwendung
- [ ] Audit-Trail

---

<a id="12-akzeptanzkriterien"></a>
<a id="acceptance-criteria"></a>
## 12. Akzeptanzkriterien [acceptance-criteria]

- [ ] Feature-Flag/Config-Eintrag für Wissenspräsentation ist functional
- [ ] Markdown-Output wird im konfigurierten Verzeichnis erzeugt
- [ ] Originalversion ist versioniert und nachvollziehbar
- [ ] Interne Links sind konsistent und funktionieren
- [ ] Ausgabe ist SSG-komplett (z. B. mit Hugo/Jekyll testbar)
- [ ] Tests für Content-Generierung und Versionierung

---

<a id="13-referenzen"></a>
<a id="references"></a>
## 13. Referenzen [references]

- Ki-Knowledge Config System: `ki_core.config.Config`
- Knowledge Blocks: (später)
- Static Site Generators: Hugo, Jekyll, MkDocs (kompatibel, nicht fest gekoppelt)
