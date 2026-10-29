# EPUB-Import: Umsetzung und erster echter Buchimport

Stand: **2026-10-29**.

## Umgesetzt

EPUB ist als Quellformat im zentralen DataLayout, im Domain-Quelleninventar,
im Schnellimport, im Datei-Upload und im Einzel-/Mix-Import verdrahtet.
Ein eigener Verwaltungsbefehl erlaubt die Auswahl relativ zum EPUB-Ordner.
Bestehende Layoutmigrationen berücksichtigen das Format ebenfalls.

Die Konvertierung liegt Django-unabhängig in `integrations/epub_ingest.py`;
`services/epub_import.py` materialisiert Markdown. Der kleine
`django_site/epub_import.py`-Adapter registriert Original, Kapitel und
Strukturartefakt im bestehenden KnowledgeStore. Keine zusätzliche Datenbank,
keine neue Paketabhängigkeit und keine Datenbankmigration für EPUB.

Die Kapitel folgen der EPUB-Spine. Überschriften, unterstützte Textauszeichnung,
Kapitel-/Fußnotenverweise und vorhandene Metadaten werden übernommen.
Das Strukturmanifest enthält zusätzlich Navigation und ausgelassene Strukturteile.
Generierte Kapitel werden bei erneutem Import nicht über eigene Dateiänderungen
geschrieben. Die Textwerkstatt arbeitet weiterhin auf Markdown-Snapshots und
eigenen Arbeitskopien.

## Tatsächlich importiert

In der Domain **`anthro-ag`** wurde `epub/GA193.epub` importiert:

- EPUB-Titel: **GA193 - Der innere Aspekt des sozialen Rätsels**.
- **11 Markdown-Abschnitte**, einschließlich der Hinweise.
- Ziel: `anthro-ag/md/epub/GA193-138697960163b3a4/`.
- Alle **11 Kapitel sind im echten Werkstatt-Quelleninventar auswählbar**.
- SHA-256 des Originals stimmt mit dem gespeicherten Herkunftsmanifest überein.
- Das EPUB enthält keine Autorenmetadaten; es wurde kein Autor erfunden.

Ein reines Bild-Cover wurde mit Warnung ausgelassen. Die eigene
Navigationsdatei wurde nicht als leeres Textkapitel übernommen; ihre Struktur
bleibt im Manifest. Zwei Navigationslinks auf die ausgelassenen Cover-/
Navigationsdokumente sind ausdrücklich als nicht übernommene Links gemeldet.
Das sind keine ausgelassenen Vortragstexte.

Dieser Import hat neue Markdown-Dateien und KnowledgeStore-Einträge erzeugt,
aber weder das EPUB verändert noch einen Dienst neu gestartet oder
Django-Migrationen ausgeführt.

## Überprüfung und Grenzen

**308 gezielte Tests** für Konvertierung, komplette Importstrecke,
Ordner-/Uploadrouting, Layoutmigrationen, bestehende Formate, Widgets und
Paketinhalt bestanden. Zusätzlich bestanden **67 Werkstatt-/Modulgrenztests**;
der Django-Systemcheck war ohne Befund.

Die synthetischen EPUB-Fixtures decken unter anderem Lesereihenfolge,
Kapitelverweise, Textstruktur, Metadaten, Cover/Nav in der Spine, zulässige
XHTML-Doctypes, ungültige Archive/XML, Pfadgrenzen, Verschlüsselung und
Ressourcenlimits ab. Der echte Buchimport und die anschließende Inventarprüfung
sind davon getrennte praktische Nachweise. Kein Modellaufruf und keine
inhaltliche Bewertung des Buches fanden statt.

Keine OCR, keine Bildextraktion, kein DRM-Umgehen und keine originalgetreue
Rekonstruktion von Buchseiten oder Typografie.

[Bedienungsanleitung und Grenzen](../guides/epub-import.md)
