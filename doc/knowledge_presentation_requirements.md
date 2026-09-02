# Knowledge Presentation Feature – Anforderungen

**Arbeitstitel:** Knowledge Presentation (Wissenspräsentation)  
**Status:** Anforderungsphase (Phase 1)  
**Datum:** 2026-09-02

---

## 1. Zielbild

Eine **browsbare Wissens-Website als Markdown-Quellbestand** erzeugen, die später mit einem Static Site Generator (SSG) gebaut und aktualisiert werden kann.

Im ersten Schritt geht es **nur um Inhalte und Dateistruktur**, nicht um semantische Anbindung oder Knowledge-Block-Integration.

---

## 2. Scope (Phase 1)

1. Ausgabe als Markdown-Dateien inkl. sinnvoller Ordnerstruktur.
2. Navigierbare Struktur über Seitenhierarchie und interne Links.
3. Nutzung vorhandener Quelldokumente als inhaltliche Basis.
4. Versionierbare „Originalversion" als Startstand.
5. Vorbereitung auf KI-gestützte, halbautomatische Weiterentwicklung/Versionierung.

---

## 3. Nicht im Scope (jetzt explizit ausgeschlossen)

1. Keine semantische Technologie-Integration.
2. Keine Knowledge-Blocks-Anbindung.
3. Kein finales SSG-Setup/Theme/Build-Pipeline-Zwang (nur SSG-kompatibler Content-Output).

---

## 4. Konfiguration

### 4.1 Config-Eintrag

Neuer Config-Eintrag für den Arbeitstitel der Präsentation und Ausgabeziel.

**Kandidat:** `knowledge_presentation_title` im ki-core Config-System

### 4.2 Default-Ausgabepfad

```
<data_root>/data_out/<domain>/<working_title>
```

**Komponenten:**
- `data_root`: aus vereinheitlichtem `ki-core` Config-System
- `domain`: aus aktiver/übergebener Domäne  
- `working_title`: konfigurierbar (Arbeitstitel der Wissenspräsentation)

---

## 5. Input-/Quellenanforderungen

1. Es gibt definierte Quelldokumente als Referenzbasis für den ersten Entwurf.
2. Inhalte sollen **sinngemäß möglichst vollständig** übernommen werden.
3. Der erste ausgeleitete Stand wird als **Originalversion** festgehalten.
4. Quelldokumente können aus verschiedenen Quellen stammen:
   - Markdown-Blöcke (Wissensbase)
   - Externe Dokumente/URLs
   - Importierte Inhalte (z. B. aus älteren Quellen)

---

## 6. Content-Generierung (Phase 1 Verhalten)

1. Erzeuge Startseite und thematische Unterseiten als Markdown.
2. Lege eine klare Informationsarchitektur fest:
   - Kapitel/Themen/Unterthemen
   - Sinnvolle Hierarchie-Tiefe
3. Erzeuge interne Verlinkung für Browsing.
4. Schreibe reproduzierbar in den konfigurierten Zielordner.
5. Überschreibe nicht unkontrolliert; Versionierung muss nachvollziehbar sein.

---

## 7. Versionierung & Evolvierbarkeit

1. Originalversion wird als baseline versioniert (z. B. `v1-original`).
2. Spätere KI-unterstützte Überarbeitungen bauen darauf auf.
3. Änderungen sollen halbautomatisch erzeugbar und versionierbar sein.
4. Markdown-Struktur muss diff-freundlich sein (saubere Diffs über Versionen).
5. Metadaten/Frontmatter können zur Versionsverfolgung genutzt werden.

---

## 8. Qualitätsanforderungen

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

## 9. Architektur-Skizze

```
<data_out>/<domain>/<working_title>/
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

## 10. Offene Punkte für die Umsetzung

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

## 11. Implementation-Roadmap (Phaseneinteilung)

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

## 12. Akzeptanzkriterien

- [ ] Feature-Flag/Config-Eintrag für Wissenspräsentation ist functional
- [ ] Markdown-Output wird im konfigurierten Verzeichnis erzeugt
- [ ] Originalversion ist versioniert und nachvollziehbar
- [ ] Interne Links sind konsistent und funktionieren
- [ ] Ausgabe ist SSG-komplett (z. B. mit Hugo/Jekyll testbar)
- [ ] Tests für Content-Generierung und Versionierung

---

## 13. Referenzen

- Ki-Knowledge Config System: `ki_core.config.Config`
- Knowledge Blocks: (später)
- Static Site Generators: Hugo, Jekyll, MkDocs (kompatibel, nicht fest gekoppelt)
