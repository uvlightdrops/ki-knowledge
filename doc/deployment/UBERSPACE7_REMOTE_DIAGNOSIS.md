---
project: "ki-knowledge"
scope: "deployment"
created: "2026-11-05 15"
updated: "2026-11-05 15"
update_reason: "Present general research on AI-assisted remote diagnosis without incident history"
status: "active"
agent_project: "ki-knowledge"
---

# Recherche: KI-gestuetzte Remote-Diagnose auf Uberspace 7

## Ziel und Abgrenzung

Diese Recherche vergleicht Ansaetze zur Diagnose einer entfernten
Python-/Django-Anwendung: lokale KI-Assistenz mit SSH-Zugriff, Agenten direkt
auf dem Host, Cloud-Agenten und Remote-Debugger. Im Mittelpunkt stehen
Uberspace 7, rootloser Betrieb und die bestehende stackctl-/Supervisor-Linie.
Sie ist keine Installationsanleitung und keine Freigabe fuer autonome
Eingriffe auf einem laufenden Server.

**Empfehlung:** Mit lesenden, einzeln freigegebenen SSH-Diagnosekommandos
beginnen. Erst wenn deren Befunde nicht ausreichen, gezielte Instrumentierung
oder einen abgesicherten Remote-Debugger einsetzen. Ein dauerhaft laufender
Agent auf dem App-Host ist keine Voraussetzung fuer KI-Unterstuetzung.

Recherche am 2026-11-05. Produktanforderungen koennen sich aendern;
Agenten- und Debugger-Kompatibilitaet auf einem konkreten U7-Host wurde
nicht getestet.

## 1. Moegliche Betriebsmodelle

| Variante | Ausfuehrungsort | Bewertung fuer U7 |
|---|---|---|
| Lokaler Agent mit freigegebenen SSH-Kommandos | Agent lokal, Diagnose auf U7 | Erste Wahl; keine weitere Agent-Laufzeit auf dem App-Host |
| Copilot CLI in einer SSH-Sitzung | Werkzeuge auf U7, Modellanfragen extern | Moeglich, sofern die konkrete Version auf U7 startet; nicht bestaetigt |
| Copilot Cloud Agent | GitHub-Umgebung | Fuer reproduzierbare Codekorrekturen; kein automatischer Zugriff auf laufende U7-Prozesse |
| JetBrains Gateway/Remote Development | IDE-Backend auf U7 | Aktuelle glibc-Anforderungen passen nicht zur dokumentierten U7-Basis |
| Lokale IDE mit Remote-Debugger | IDE lokal, Debugkomponente auf U7 | Gezielte zweite Diagnose-Stufe; Kompatibilitaet und Zugriffsschutz separat pruefen |

### Lokaler Agent mit SSH-Werkzeugen

Der Agent bleibt auf dem Entwicklungsrechner. Nur klar begrenzte Kommandos
werden ueber SSH auf dem Zielhost ausgefuehrt. Das vermeidet eine zusaetzliche
Agent-Installation und Authentifizierung auf dem App-Server.

Die Berechtigung folgt jedoch dem verwendeten SSH-Account: Auch ein lokal
laufender Agent kann damit auf entfernte Geheimnisse zugreifen oder Dienste
veraendern. Deshalb Kommandos einzeln freigeben, lesende Diagnose von
Eingriffen trennen und keine pauschale Shell-Freigabe als Isolation betrachten.
Es darf nur freigegebene, nicht geheime Ausgabe in den Modellkontext gelangen.

### Agent direkt auf dem Host

Eine ueber SSH gestartete CLI arbeitet auf dem Server. Die Modellinferenz
kann extern stattfinden; CLI, Werkzeuge und Kontextverarbeitung benoetigen
trotzdem lokale Ressourcen. Ein installiertes Ollama ist fuer Copilot CLI
nicht erforderlich. Kompatibilitaet, Berechtigungen und Datenschutz sind
voneinander getrennte Voraussetzungen.

Ein interaktiver, zeitlich begrenzter Diagnoseauftrag ist etwas anderes
als ein Supervisor-Daemon mit dauerhaftem Zugriff auf das App-Konto.
Fuer Letzteren besteht hier keine Betriebsempfehlung.

### Cloud-Agent

Ein Cloud-Agent untersucht einen Checkout in seiner eigenen Umgebung.
Er eignet sich fuer reproduzierbare Tests und Codekorrekturen, kennt aber
nicht automatisch Prozesszustand, lokale Overrides oder Dateirechte auf U7.
Zugangsdaten zum Deployment-Host sollten nicht allein fuer diese
Untersuchung in eine Cloud-Umgebung kopiert werden.

## 2. Plattform- und Produktanforderungen

### Uberspace 7

Das U7-Handbuch nennt maximal 1,5 GB RAM pro Account und CPU-Drosselung bei
uebermaessiger Nutzung. Dieses Budget teilen sich Anwendung, Datenbank und
weitere Accountprozesse. Zusaetzliche IDE-Backends und Agenten koennen damit
direkt den App-Betrieb beeintraechtigen.

Die Uberspace-Lab-Diskussionen nennen fuer U7 CentOS 7 und glibc 2.17.
Massgeblich fuer die konkrete Installation bleibt der Hostbefund:

```bash
uname -m
getconf GNU_LIBC_VERSION
```

Kein Austausch der Host-glibc und keine alte Agent-Version nur zum Umgehen
aktueller Anforderungen als Standardloesung.

### GitHub Copilot CLI

GitHub dokumentiert Linux-Unterstuetzung, Installation ohne root nach
`~/.local` und alternativ npm mit Node.js mindestens 22. Ein interaktives
`/login` ist moeglich; ein dauerhaft hinterlegtes Token ist nicht zwingend
noetig.

Eine allgemeine Linux-Angabe bestaetigt keine Kompatibilitaet mit dem alten
U7-System. Native Komponenten koennen an der glibc scheitern; npm umgeht
native Anforderungen nicht automatisch. Eine offiziell garantierte
U7-Unterstuetzung wurde bei dieser Recherche nicht gefunden.

### JetBrains Remote Development

JetBrains verlangt seit 2025.1 fuer IntelliJ-basierte IDEs auf Linux x64
glibc mindestens 2.28, ausdruecklich auch in Remote-Development-Umgebungen.
Das passt nicht zur dokumentierten U7-Basis mit 2.17.

Ein alter IDE-Backend-Build ist keine empfohlene Dauerloesung. Eine lokale
IDE mit SSH-Dateizugriff oder einem passenden Remote-Debugprotokoll ist
architektonisch etwas anderes als ein vollstaendiges Remote-IDE-Backend.

## 3. Berechtigungen, Geheimnisse und Werkzeugfreigaben

Ein Agent im selben Unix-Account hat potenziell Zugriff auf `creds.yaml`,
`.pgpass`, SSH-Schluessel und private Dokumente. Ein vertrauenswuerdiger
Projektordner und Werkzeugfreigaben sind **keine harte Sicherheitsgrenze**.
Auch lesende Werkzeuge koennen Geheimnisse in Modellkontext oder Protokolle
uebertragen.

Vor Beginn festlegen:

- Welche konkreten Diagnosekommandos sind erlaubt?
- Welche Ausgaben duerfen extern verarbeitet werden?
- Welche Daten und Pfade sind ausgeschlossen?
- Welche Eingriffe benoetigen eine gesonderte Zustimmung?

Kein `--allow-all-tools`, kein Agentstart aus dem gesamten Home-Verzeichnis
und keine ungefilterten Exporte von `env`, `/proc/PID/environ`,
Supervisor-Konfigurationen oder vollstaendig aufgeloester App-Konfiguration.
Auch Logs und Prozessargumente koennen sensible Daten enthalten.

Eine restriktive umask ist fuer private App-Daten sinnvoll: `077` ergibt bei
ueblichen Erstellungsrechten Verzeichnisse mit `0700` und Dateien mit `0600`.
Sie gilt pro Prozess und wird an Kindprozesse vererbt; sie ist keine
Sandbox und beschraenkt keinen Agenten mit derselben Unix-Identitaet.
Dateirechte nicht pauschal fuer Diagnosezwecke lockern.

## 4. Allgemeiner Diagnoseablauf

### A. Identitaet und Laufzeit getrennt erfassen

Dateistand und laufender Prozess sind unterschiedliche Befunde. Ein
`git pull` aktualisiert Dateien, nicht bereits importierte Python-Module.
Auch ein idempotentes `start` ist nicht gleichbedeutend mit einem Neustart.

Fuer ki-knowledge im Projektverzeichnis:

```bash
git rev-parse --short HEAD
git status --short
KI_STAGE=prod-uberspace7 ./kistack status
```

Bei Pfadfragen kann `kictl paths DOMAIN` Datenroot, Layoutversion und
vorhandene Quellverzeichnisse ausgeben. Das beschreibt einen neuen
CLI-Prozess, nicht automatisch die Konfiguration eines laufenden Webworkers.

Fuer eine konkret ermittelte eigene PID:

```bash
ps -p PID -o pid,ppid,lstart,args
readlink /proc/PID/cwd
```

Startzeit und Arbeitsverzeichnis sind Hinweise, aber kein vollstaendiger
Nachweis der geladenen Codeversion. Master, Worker, API und Hintergrundjobs
getrennt betrachten.

### B. Eine konkrete Hypothese pruefen

Ausloesende Aktion, erwartetes Verhalten und beobachtete Abweichung
festhalten. Danach die kleinstmoegliche zusaetzliche Evidenz erheben:
gezielte Logzeilen, einen einzelnen Konfigurationswert oder einen bestimmten
Prozesszustand. Nicht vorsorglich alle Daten und Logs sammeln.

### C. Eingriffe gesondert freigeben

Neustarts, Konfigurationsaenderungen, Paketinstallationen und
Debugger-Anbindungen sind keine lesende Diagnose. Umfang, moegliche
Unterbrechung und Erfolgskriterium vorher benennen. Nur die benoetigten
App-Dienste anfassen, nicht pauschal Datenbank, Tunnel oder alle
Supervisor-Programme neu starten.

Nach dem Eingriff denselben Test wiederholen und die Befunde vergleichen.
Diagnosewerkzeuge und voruebergehende Zugriffe danach wieder entfernen.

## 5. Wann ein Remote-Debugger sinnvoll ist

Wenn Logs und Prozessvergleich nicht ausreichen, kann ein Debugger
Variablen, Aufrufstapel und den konkreten Kontrollfluss zeigen.
`debugpy` dokumentiert dafuer Debug Adapter Protocol und SSH-Tunnel.
JetBrains verwendet eigene Debugger-Anbindungen; eine debugpy-Sitzung ist
nicht automatisch mit jedem JetBrains-Client kompatibel.

Fuer einen gesondert freigegebenen Testprozess gilt:

- Nur Loopback binden, niemals einen oeffentlichen Debugport anbieten.
- **Auf Shared Hosting ist auch Loopback nicht automatisch accountprivat.**
  Ein SSH-Tunnel schuetzt den Transport, verhindert aber nicht allein Zugriffe
  anderer lokaler Accounts auf den Debugport. Ohne belastbare
  Zugriffsbeschraenkung kein offener debugpy-Listener auf U7; besser lokal
  reproduzieren oder eine isolierte Testumgebung verwenden.
- Ein Debugger kann Code im Zielprozess ausfuehren. Ein Breakpoint kann
  Requests blockieren und Gunicorn-Timeouts verursachen.
- Kein `--wait-for-client` am normalen App-Dienst. Keine unkontrollierten
  Attach-Versuche an laufende produktive Worker.
- Quellstand und Pfadzuordnung zwischen lokal und remote muessen passen.
  Installation und native Komponenten des Debuggers auf U7 sind separat zu
  pruefen; fuer den Ressourcenaufschlag liegt kein belastbarer Pauschalwert vor.

## 6. Perspektive fuer ki-knowledge

Eine kleine, secretfreie Laufzeitdiagnose waere eine sinnvolle Erweiterung:
Startzeit, geladene Codeversion, Stage und aufgeloeste Pfade sollten aus dem
laufenden Dienst abfragbar sein. Das wuerde Vergleiche mit dem CLI-Befund
vereinfachen, ohne einen Agenten oder Debugger auf dem Host vorauszusetzen.

Diese Recherche implementiert weder einen solchen Endpunkt noch einen
SSH-Agenten, eine automatische Reparatur oder einen Debugger-Dienst.
Die bestehende Betriebsanleitung bleibt das
[U7-Runbook](UBERSPACE7_IMPLEMENTATION.md); die Konfigurationsschichten
beschreibt der [Konfigurationsleitfaden](../guides/YAML_CONFIG_SYSADMIN.md).

## Quellen

1. [Uberspace: Ressourcen](https://manual.uberspace.de/basics-resources/)
   und [supervisord](https://manual.uberspace.de/daemons-supervisord/):
   Accountlimits und Prozessverwaltung.
2. [Uberspace/lab#1680](https://github.com/Uberspace/lab/issues/1680)
   und [Uberspace/lab#1346](https://github.com/Uberspace/lab/issues/1346):
   primaere Projekt-Diskussionen zur alten U7-glibc und inkompatiblen Binaries;
   keine allgemeine Freigabe fuer Agenten.
3. [GitHub: Copilot CLI installieren](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/install-copilot-cli):
   Installationswege, npm-Voraussetzung und Authentifizierung.
4. [GitHub: Copilot CLI](https://docs.github.com/en/copilot/concepts/copilot-surfaces/copilot-cli):
   Werkzeugfreigaben und Grenzen vertrauenswuerdiger Verzeichnisse.
5. [GitHub: Cloud-Sandboxes](https://docs.github.com/en/copilot/concepts/security-governance-and-network-settings/about-cloud-sandboxes):
   Lokale CLI-Sitzungen und GitHub-gehostete Ausfuehrung.
6. [JetBrains: glibc-Anforderungen ab 2025.1](https://blog.jetbrains.com/idea/2025/01/updated-system-requirements-for-linux-gnu-c-library-glibc/):
   Mindestversion 2.28 auch fuer Remote Development.
7. [debugpy README](https://github.com/microsoft/debugpy/blob/main/README.md)
   und [CLI-Referenz](https://github.com/microsoft/debugpy/wiki/Command-Line-Reference):
   Listener, Codeausfuehrungsrisiko und SSH-Tunnel.
8. [Supervisor-Konfiguration](https://supervisord.org/configuration.html#program-x-section-settings)
   und [Python: os.umask](https://docs.python.org/3/library/os.html#os.umask):
   Prozessbezogene Dateirechte.
