# YAML-Konfiguration in ki-knowledge

Stand: 2026-10-29. Diese Seite ist der projektspezifische Einstieg, keine zweite
Kopie der gemeinsamen Konfigurationsdokumentation.

## Gemeinsame Grundlagen

- [Kanonischer Sysadmin-Leitfaden](../../../yaml_cfg_wizard/doc/YAML_CONFIG_SYSADMIN.md):
  Schichten, CLI, Editor-Grenzen, Identitaet und Betrieb im gesamten Workspace.
- [Konfigurationskonzepte](../../../yaml_cfg_wizard/doc/YAML_CONFIG_CONCEPTS.md):
  Architektur und weiterfuehrende Konzepte.
- [Projektuebergreifende Administration](../../../../dev_doc/yaml_config_administration.md)
  in `~/dev_doc`.

Die bisherige Vollkopie dieser Anleitung war vor der Umstellung byte-identisch
mit der kanonischen Quelle im Wizard-Repository. Sie wird hier nicht weiter
dupliziert. Historische Statusaussagen in der gemeinsamen Anleitung sind kein
Nachweis eines aktuellen Rollouts dieses Projekts.

## Was fuer dieses Projekt gilt

`ki_knowledge.app_config.AppConfig` liest die ueber ki-core aufgeloeste
Konfiguration. Die Reihenfolge von niedrig nach hoch ist:

1. Schema-Defaults.
2. `config/defaults/`.
3. `ki.yaml`.
4. Aktives Profil, falls ausgewaehlt.
5. Aktive Stage (`KI_STAGE` oder `config/stages/.active_stage`).
6. `config/runtime/runtime.yaml`.
7. `KI_CFG_*`-Umgebungsvariablen.
8. `creds.yaml`.

Kommandos aus Dokumenten werden im **Projektverzeichnis** ausgefuehrt, nicht im
Verzeichnis der Anleitung. Hostlokale Dateien und Secrets bleiben ausserhalb
der Dokumentation.

## Betrieb und Bearbeitung

- [Django-/Stack-Betrieb](DJANGO_DEV.md): Start, Vordergrundmodus, Stages,
  Port-Overrides, lokale Dienste und Cluster-Ziele.
- Der aktuelle Provider-Schluessel ist `llm.provider`; `llm.default_provider`
  wird vom aktuellen Core-Schema nicht akzeptiert.
- Die Stack-Definition liegt in `config/defaults/stack.yaml`, nicht in
  Example-Startskripten.
- [Live-Konfiguration](live-settings.md) unter `/settings/config/`:
  schema-basierte gemeinsame Oberfläche für aktive Superuser, mit
  Revisionsschutz, Vererbung und ausdrücklich gekennzeichneten Neustartgrenzen.
- Der begrenzte Sync-Editor unter `/settings/config/sync/` bearbeitet
  `public_url` und `federation_id` im Runtime-Layer. Weitere Grenzen und
  Voraussetzungen stehen im Betriebsleitfaden.
- DB-Overrides der Sync-Administration sind von YAML-Layern zu unterscheiden:
  Ein bestehender `NodeConfig`-Eintrag hat fuer die dort verwalteten Felder
  Vorrang.

## Dokumentationspflege

Generische Regeln werden an der verlinkten gemeinsamen Quelle gepflegt.
Projektspezifische Abweichungen werden hier oder im Betriebsleitfaden ergaenzt.
Nicht aus einer vorhandenen YAML-Datei auf einen installierten, getesteten oder
laufenden Dienst schliessen.
