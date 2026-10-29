# Dokumentation: ki-knowledge

Die Dokumentation ist nach Zweck gegliedert. **Anleitungen, Konzepte und
historische Berichte sind nicht derselbe Implementierungsstand.**

## Hier anfangen

- [Schnellstart und Projektueberblick](../README.md).
- [Aktuelle Bestandsaufnahme](tracking/project-inventory-2026-10-28.md):
  Groesse, Verantwortlichkeiten, Engpaesse und priorisierte Bereinigung.
- [Django und Service-Stack betreiben](guides/DJANGO_DEV.md).
- [Konfiguration administrieren](guides/YAML_CONFIG_SYSADMIN.md).
- [Paket-Build und Quellbaum](guides/packaging.md).
- [Quellen, Workspace und Output unterscheiden](architecture/source-workspace-and-workflow-concept.md).
- [Textwerkstatt-Konzept](architecture/knowledge-workbench-concept.md) und
  [Editor-Entwurf als Markdown](features/knowledge-workbench-design.md) —
  Zielbild für persistente Markierungen, Relationen und KI-Überarbeitung.
  Die erste Umsetzung E0–E4 beschreibt die
  [Textwerkstatt-Anleitung](guides/text-workbench.md).
- [Vollstaendiger Dokumentindex](INDEX.md).

## Bereiche

| Bereich | Inhalt und Verbindlichkeit |
|---|---|
| [architecture/](architecture/) | Modelle, Systemgrenzen und fachliche Konzepte; Status im jeweiligen Dokument beachten. |
| [guides/](guides/) | Bedienung, Betrieb und Entwicklung dieses Projekts. |
| [features/](features/) | Fachfunktionen, Beispiele und Anforderungen; keine pauschale Fertigmeldung. |
| [integration/](integration/) | Anbindung externer Systeme und Schwesterpakete. |
| [refactorings/](refactorings/) | Umbaukonzepte und Migrationsplaene; nicht automatisch umgesetzt. |
| [tracking/](tracking/) | Datierte Bestandsaufnahmen und detaillierte Abdeckungsberichte. |
| [archive/](archive/) | Historische Berichte, ueberholte Roadmaps und alte Jira-Bezeichnungen. |

`doc/` bleibt der **einzige** projektspezifische Dokumentationsbaum; ein zweites
`docs/` wird nicht parallel gefuehrt. Dateinamen wurden bei der Einordnung
beibehalten. Relative Verweise in verschobenen Dokumenten und Referenzen aus
Code und Tests wurden angepasst. Befehlsbeispiele gelten weiterhin relativ
zum Repository-Root.

## Gemeinsame Dokumentation

Die Aufteilung folgt dem
[Dokumentationsleitfaden](../../../dev_doc/DOCUMENTATION_ORGANIZATION_GUIDE.md)
in `~/dev_doc`: generische Regeln dort, Projektumsetzung hier.

- [Server-Management](../../../dev_doc/server-mngm/SERVER_MANAGEMENT_README.md).
- [Gemeinsame CLI-Architektur: historische Entwuerfe](../../../dev_doc/cli-management/README.md).
- [Kanonische YAML-Betriebsanleitung](../../yaml_cfg_wizard/doc/YAML_CONFIG_SYSADMIN.md).

Die externen Verweise setzen das bekannte Workspace-Layout voraus; sie sind
nicht Bestandteil eines alleinstehenden ki-knowledge-Checkouts. `doc/link`
bleibt als vorhandener lokaler Daten-Symlink unveraendert und ist kein Teil
dieses Dokumentationsbaums.
