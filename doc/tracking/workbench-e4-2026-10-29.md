# Textwerkstatt E4: kontrollierte KI-Überarbeitung

Stand: **2026-10-29**. Implementiert im Arbeitsbaum, noch nicht als
Live-Aktualisierung der Anwendungsdatenbank ausgeführt.

## Fachlicher Umfang

E4 ergänzt eine getrennte Aktion neben dem Gespräch: Eine gespeicherte Passage
einer eigenen Arbeitskopie wird mit einem ausdrücklichen Auftrag überarbeitet.
Das Ergebnis ist zunächst nur ein gespeicherter Vorschlag, kein geänderter Text.

Die Oberfläche bietet einen Monaco-Diff, zusätzlich beide Fassungen als reinen
Text, einen bearbeitbaren Ersatztext sowie **Übernehmen** und **Verwerfen**.
Originalauswahl und ursprüngliche KI-Fassung bleiben erhalten, auch wenn der
Benutzer vor der Annahme manuell korrigiert. Leerer Ersatztext ist eine bewusste
Löschung, kein stiller Fehler-Fallback.

Bei Annahme entstehen genau eine neue unveränderliche Revision und ein
Herkunftsbezug auf den Vorschlag. Annotationen verbleiben an ihren ursprünglichen
Revisionen. Weder Quelldateien noch KnowledgeStore, InfoSite-Ausgaben oder
Wagtail-Seiten werden beschrieben.

## Technischer Schnitt

| Fläche | Aufgabe |
|---|---|
| `workbench_models.WorkbenchProposal` und Migration `0023_workbench_proposals` | Vorschlag, Basis, Status, Kontext und angenommene Revision |
| `workbench_proposals.py` | Validierung, Providerauftrag, Fehlerzustände und transaktionale Entscheidung |
| `views_workbench.py` / `workbench_urls.py` | Session-/CSRF-geschützte HTTP-Adapter |
| `ProposalPanel.tsx` | Auswahl, Auftrag, Referenzen, gespeicherte Vorschläge und Entscheidung |
| `ChangeComparison.tsx` | Reiner Original-/Ersatzvergleich ohne Domain- oder API-Abhängigkeit |

Erzeugung und Annahme bleiben getrennte Operationen. Die vorhandene
`llm_provider`-Anbindung und Validierungs-/Revisionshelfer werden wiederverwendet;
es entsteht kein zweiter Providerclient und kein allgemeines Agenten-Framework.
Der kleine Vergleichsbaustein kann später auch außerhalb der Werkstatt benutzt
werden. Ein gemeinsames Paket mit Assist ist noch nicht extrahiert.

### Persistente Zustände und Fehler

- `generating`: reservierte Provideranfrage; keine offene DB-Transaktion während
  der externen Generierung.
- `pending`: vollständiger, noch nicht angenommener Vorschlag.
- `failed`: Providerfehler, ungültige strukturierte Antwort oder abgelaufene
  Generierungsreservierung.
- `accepted` / `rejected`: ausdrücklich getroffene Entscheidung.

Die Erzeugung erwartet strukturiertes JSON mit `replacement_markdown` und
`rationale`. Ungültige Antworten werden nicht durch heuristisches Extrahieren
irgendwelcher Antwortteile als Erfolg behandelt. Unerwartete Programmfehler
bleiben Serverfehler, statt als erfolgreiche oder leere Vorschläge zu erscheinen.

Eine Anfrage-ID bezeichnet einen festen Auftrag. Identische Wiederholung startet
keinen zweiten Providerlauf; dieselbe ID mit anderen Eingaben ist ein Konflikt.
Nach unklarer Übernahmeantwort wird derselbe Ersatztext erneut geprüft.
Gleiche Annahme erzeugt keine zweite Revision, eine abweichende Wiederholung
wird abgewiesen.

### Rechte, Koordinaten und Konflikte

Jeder Zugriff ist an Eigentümer und aktive Domain gebunden. Schreibziel ist
nur eine eigene Arbeitskopie, niemals der Quellsnapshot. Auswahl und Originaltext
werden mit Unicode-Codepoint-Koordinaten und dem unveränderlichen Basisstand
abgeglichen. Die Annahme sperrt und prüft den aktuellen Dokumentstand innerhalb
einer Transaktion; ein zwischenzeitlich gespeicherter Stand wird nicht überschrieben.

Ein einzelner zusammenhängender Bereich ist erlaubt, keine beliebigen
Mehrdatei-Patches. ETag-Prüfung, Textgrößen- und Kontextgrenzen gelten weiterhin.

### Quellen und fachliche Bewertung

Der Auftrag sendet die Auswahl und ausschließlich bewusst gewählte zusätzliche
Referenzrevisionen. Das Kontextmanifest hält den tatsächlich übertragenen Text
fest. Auftrag, Promptversion, Provider und Modell bleiben beim Vorschlag.

Quelltexte werden als Material, nicht als neue Systemanweisungen behandelt.
Das ist eine Promptgrenze, keine Garantie gegen jede Fehlinterpretation eines
Modells. Fachbegriffe und Autorenperspektiven sollen erhalten bleiben.
Eine plausible Begründung oder ein Quellenmarker beweisen weder Quellentreue
noch Wahrheit. Es gibt keine automatische Veröffentlichung oder Wahrheitsprüfung.

## Isolierte Überprüfung

Im abschließenden Lauf:

- **93 Python-Tests** für bestehende Werkstatt, neue Vorschläge, Quellenbrowser,
  Assets, Paketinhalt und Modulgrenzen bestanden.
- **3 Frontendtests** für Unicode-Koordinaten bestanden.
- **7 echte Browserabläufe** gegen einen eigenen Django-Testserver bestanden:
  bisherige Quellen-/Annotations-/Revisions-/Gesprächsabläufe plus Vorschlag,
  manuell korrigierte Annahme mit Neuladen, Verwerfen/ungültige Antwort und
  parallel geänderter Serverstand.
- TypeScript-/Produktionsbuild erfolgreich; Django-Systemcheck und
  Migrationsvergleich nach vollständigem Laden der Modelle ohne neue Abweichung.

Die Backendfälle umfassen unter anderem Eigentümer-/Domaingrenzen, CSRF,
Provider- und Formatfehler, Unicode, veraltete Basen, Löschung,
Annahmewiederholung, Rollback und konkurrierende Annahmeversuche. Die Browser-
Provider sind kontrollierte Testadapter, keine Bewertung realer Modellqualität.
SQLite-basierte Tests ersetzen keinen gesonderten PostgreSQL-Lasttest.

Die Browserprüfung fand beim ersten Durchlauf eine durch doppelte React-Keys
verursachte Editorverdoppelung. Unterschiedliche Komponenten erhalten nun
unterschiedliche Keys; bestehende und neue Abläufe wurden danach erneut geprüft.
Die endgültigen lokalen Assets sind mitgebaut. Der bekannte Hinweis auf das
große Monaco-Bundle bleibt sichtbar; keine zusätzliche CDN-Abhängigkeit.

## Inbetriebnahme und Grenzen

Die laufende Anwendungsdatenbank wurde nicht migriert und der Anwendungsserver
nicht neu gestartet. Nach Sicherung der Datenbank:

```bash
.venv/bin/python manage.py migrate
```

Anschließend den bestehenden Server über seinen bisherigen Startweg neu starten,
bei PyCharm mit `--noreload` ausdrücklich Stop/Debug verwenden. Ein Zielbetrieb
mit `collectstatic` benötigt auch die normale Staticfiles-Aktualisierung.

Vorschläge und vollständige Anfragekontexte bleiben wie Gespräche privat in der
Anwendungsdatenbank gespeichert. Automatische Aufbewahrungsfristen,
Endnutzer-Löschworkflow und Team-Sharing sind weiterhin nicht implementiert.
Keine neue Markdown-Lesevorschau, kein Streaming, keine E5-Publikationsbrücke
und keine E6-Auslagerung.

[Bedienungsanleitung](../guides/text-workbench.md) ·
[Kurzinventur zur Beherrschbarkeit](project-inventory-followup-2026-10-29.md)
