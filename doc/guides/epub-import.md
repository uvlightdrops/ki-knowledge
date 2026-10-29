# EPUB-Bücher als Markdown-Quellen importieren

EPUB ist für Textarbeit normalerweise der bessere Eingang als ein gescanntes
PDF: Der Text liegt bereits digital vor und die Lesereihenfolge ist im
EPUB-Paket festgelegt. Eine OCR wird bei diesem Import nicht ausgeführt.

## Ordner und Bedienung

Im aktuellen Datenlayout liegt das Original unter:

```text
<Datenwurzel>/<Domain>/epub/<Buch>.epub
```

Für `anthro-ag` also im selbst angelegten Ordner `anthro-ag/epub/`.
Es ist keine eigene Domainkonfiguration für dieses Format erforderlich.
Ein gesetztes `KNOWLEDGE_EPUB_ROOT` überschreibt wie bei anderen Quelltypen
die Formatwurzel; darunter folgt die Domain.
Das Format wird auch in den älteren Layoutversionen korrekt aufgelöst und
bei einer ausdrücklich gestarteten Layoutmigration mitgenommen. Für EPUB
allein ist weder eine Layout- noch eine Datenbankmigration nötig.

Nach einem Neustart der Anwendung erscheint EPUB in **Data Sources**:

1. Die richtige Domain wählen.
2. Unter **Quellen** die EPUB-Datei importieren, oder über den Schnellimport
   den Ordner **EPUB** importieren. Auch der normale Datei-Upload akzeptiert
   `.epub` und legt das Original im EPUB-Ordner ab.
3. Die erzeugten Markdown-Kapitel sind anschließend normale Quellen.
4. In der **Textwerkstatt** das gewünschte Kapitel erfassen und daraus eine
   eigene Arbeitskopie anlegen. Das Buchoriginal wird nicht bearbeitet.

Einzelimport über die bestehende Django-Verwaltung:

```bash
.venv/bin/python manage.py import_epub --domain anthro-ag --file GA193.epub
```

`--file` ist relativ zum EPUB-Ordner dieser Domain, kein beliebiger Serverpfad.
Ohne `--file` werden alle EPUBs des Domainordners importiert.

## Ergebnis und Herkunft

```text
<Domain>/
  epub/<Buch>.epub
  md/epub/<Dateiname>-<Inhaltshash>/
    book.json
    0001.md
    0002.md
    ...
```

Die Kapitelnummern folgen der EPUB-**Spine**, nicht alphabetisch sortierten
ZIP-Einträgen. Der Import erhält die unterstützte Textstruktur und speichert
Buchtitel, Autoren, Sprache, Kennung, ursprüngliche Kapitelpfade und
Konvertierungswarnungen in `book.json`. Die Kapitelquellen tragen zusätzlich
den Bezug zum ursprünglichen Buch und dessen SHA-256 im KnowledgeStore.
Die Buchstruktur liegt dort als `reference_structure`-Artefakt, nicht als
erfundene Wissensrelation oder KI-Erkenntnis.

Das Original und jedes erzeugte Kapitel werden getrennt registriert:
das EPUB als Herkunftsquelle, die Markdown-Dateien als bearbeitbare
Eingangstexte für die bestehende Pipeline. Die Werkstatt benötigt weiterhin
kein InfoSite-Projekt. Autorentexte bleiben eigene, versionierte Arbeitskopien.

Identischer Import verwendet dasselbe Konvertierungsverzeichnis. Veränderte
EPUB-Inhalte erzeugen ein neues, inhaltsadressiertes Verzeichnis; alte Kapitel
und bestehende Snapshots bleiben erhalten. Hat jemand generierte Kapitel auf
der Festplatte verändert, bricht ein erneuter Buchimport ausdrücklich ab,
statt die Änderungen zu überschreiben. Für eigene Änderungen daher die
Arbeitskopie in der Werkstatt verwenden.

## Grenzen

- EPUB ist kein garantierter Klartext: Verschlüsselte Inhalte bzw. DRM werden
  ausdrücklich abgewiesen, nicht umgangen.
- Ein reines Bild-/Scan-EPUB benötigt einen separaten OCR-Prozess.
- Buchtypografie, CSS, Seitenlayout und zuverlässige gedruckte Seitenzahlen
  werden nicht rekonstruiert. Seitenverweise sollten nicht aus der EPUB-
  Kapitelnummer abgeleitet werden.
- Nicht unterstützte Inhalte werden mit Warnungen sichtbar gemacht.
  Eingebettete Bilder werden nicht als neue Bildsammlung extrahiert.
  Ein erkanntes reines Bild-Cover wird mit Warnung ausgelassen; seine Herkunft
  bleibt im Strukturmanifest vermerkt.
  Eine reine Navigationsdatei wird ebenfalls nicht zu einem leeren Kapitel;
  ihr Inhaltsverzeichnis bleibt als Metadaten erhalten.
  Skripte und aktive Inhalte werden nicht ausgeführt.
- ZIP-/XML-Inhalte werden begrenzt und ohne Entpacken beliebiger Archivpfade
  verarbeitet. Es gibt keine externen Downloads beim Konvertieren.
- Ein einzelnes Markdown-Kapitel darf höchstens 2 MiB groß sein, damit es
  anschließend als Werkstatt-Snapshot erfasst werden kann.
- Dateierzeugung und KnowledgeStore-Registrierung sind keine gemeinsame
  Transaktion: Bei einem Storefehler können schon erzeugte Kapitel bestehen.
  Der Import meldet den Fehler; ein Wiederholen prüft die vorhandenen Dateien
  und registriert sie erneut. Es gibt keinen neuen Hintergrundworker.

Die Inhalte müssen zur eigenen Nutzung berechtigt vorliegen. Diese Funktion
erteilt keine Veröffentlichungsrechte und publiziert nichts.

[Umsetzungsbericht und erster praktischer Buchimport](../tracking/epub-import-2026-10-29.md)
