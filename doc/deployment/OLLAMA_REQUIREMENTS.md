---
project: ki-knowledge
scope: deployment
created: "2026-11-03 02"
updated: "2026-11-03 02"
update_reason: "Dimensionierung eines dedizierten Ollama-Servers fuer den Uberspace-Betrieb"
status: draft
agent_project: ki-knowledge
---

# Dedizierter Ollama-Server: Anforderungen

## Ziel und Annahmen

ki-knowledge laeuft auf [Uberspace 7](UBERSPACE7_IMPLEMENTATION.md) oder
[Uberspace 8](UBERSPACE8_IMPLEMENTATION.md); Ollama auf einem separaten
Root-Server. CPU, RAM und Diskspace sind erweiterbar. Ob eine dedizierte
GPU bzw. GPU-Passthrough buchbar ist, ist noch offen.

Zielbild: Embeddings mit `nomic-embed-text` und optional interaktiver Chat
fuer zunaechst 1–2 gleichzeitige Anfragen. Die folgenden Werte sind
Planungsempfehlungen, keine gemessenen Mindestwerte oder Leistungszusagen.
Konkretes Modell, Quantisierung, Kontext und Parallelitaet vor Bestellung
festlegen und auf der angebotenen Hardware messen.

## 1. Hardwareprofile

| Ressource | Embeddings, CPU-Pilot | Empfohlen: Chat + Embeddings | Ausbau fuer groessere Modelle |
|---|---|---|---|
| CPU | 4–8 moderne dedizierte Kerne | 8–12 moderne dedizierte Kerne | 12–16 moderne dedizierte Kerne |
| System-RAM | 16 GB | 64 GB | 128 GB |
| GPU | Nicht zwingend; Durchsatz messen | Dedizierte, von Ollama unterstuetzte GPU mit 24 GB VRAM | 48 GB VRAM oder mehr, modellabhaengig |
| Disk | 100 GB SSD/NVMe | 250 GB NVMe | 500 GB–1 TB NVMe |
| Lastprofil | Begrenzte Embedding-Batches, kein Anspruch auf schnellen groesseren Chat | Quantisiertes 7–14B-Chatmodell als Ausgangspunkt, begrenzter Kontext | Etwa 30–32B als Planungsklasse; 70B separat dimensionieren |

Die Modellklassen sind Orientierung, keine Fit-Garantie. Architektur,
Quantisierung und KV-Cache koennen den Bedarf erheblich veraendern.
Auch 48 GB VRAM garantieren keinen komfortablen 70B-Betrieb mit langem Kontext.
Mehrere GPUs sind nicht automatisch so schnell oder so einfach nutzbar wie
eine ausreichend grosse GPU; Aufteilung und Interconnect gesondert bewerten.

**Beschaffungsvorschlag fuer einen flotten Einstieg:** 8–12 dedizierte
CPU-Kerne, 64 GB RAM, 250 GB NVMe und eine GPU mit 24 GB VRAM.
Vor Buchung GPU-Modell, Speicherbandbreite, Treibersupport und exklusive
Nutzbarkeit bestaetigen. VRAM-Groesse allein beschreibt nicht die Rechenleistung.

## 2. Wenn keine GPU verfuegbar ist

Ollama kann auf CPUs laufen. Ein sinnvoller CPU-Ausgangspunkt fuer kleine
Chatmodelle ist 8–16 moderne dedizierte Kerne, 32–64 GB RAM und NVMe.
Das ist jedoch **keine Zusage fuer fluessigen interaktiven Chat**.
Speicherbandbreite, CPU-Generation und Modell sind oft wichtiger als eine
hohe Zahl geteilter vCPUs. AVX2-Unterstuetzung fuer x86-64 anstreben.

Mehr RAM ermoeglicht groessere Modelle, macht deren Tokenberechnung aber
nicht automatisch schnell. Mehr Diskspace haelt mehr Modelle bereit,
beschleunigt ein bereits geladenes Modell kaum. Swap darf kein normaler
Inferenz-Arbeitsspeicher sein. Fuer Embeddings ist ein CPU-Server deutlich
plausibler als fuer anspruchsvollen Chat.

## 3. Speicherbudget und Parallelitaet

GPU-Budget = Modellgewichte + KV-Cache + Laufzeitpuffer + gegebenenfalls
gleichzeitig geladenes Embedding-Modell. Als grobe Untergrenze brauchen
8 Milliarden Parameter mit 4 Bit rund 4 GB nur fuer die Gewichte;
Quantisierungsmetadaten und alle Laufzeitkosten kommen hinzu.

Kontext umfasst Eingabe und Ausgabe. Fuer den ersten RAG-/Chatbetrieb
8k Kontext als explizites Testprofil verwenden, anschliessend 16k pruefen,
falls fachlich erforderlich. Keine pauschale 64k-/128k-Vorbelegung.
Unterstuetzte Modellkontexte beachten; Embedding-Textlaengen separat nach
Modellvertrag und Anwendung begrenzen.

Mit einer parallelen Chatverarbeitung starten, danach zwei messen.
Mehr Parallelitaet braucht zusaetzlichen Speicher und kann die Latenz pro
Nutzer verschlechtern. Embedding-Importe begrenzen/zeitlich planen, damit sie
interaktiven Chat nicht verdraengen. `OLLAMA_NUM_PARALLEL`,
`OLLAMA_MAX_LOADED_MODELS`, `OLLAMA_MAX_QUEUE` und `keep_alive` bewusst
dimensionieren, nicht moeglichst hoch setzen. Kaltes Laden und warmen Betrieb
getrennt betrachten.

Fuer das GPU-Profil mit `ollama ps` pruefen, dass das Chatmodell bei der
geplanten Last vollstaendig auf der GPU bleibt. Unbeabsichtigtes CPU-Offloading
als Kapazitaetsproblem sichtbar machen, nicht als gleichwertigen Betrieb werten.

## 4. Betrieb, Netzwerk und Einbindung

| Bereich | Anforderung |
|---|---|
| Betriebssystem | Gepflegtes Linux, beispielsweise Ubuntu 24.04 LTS; konkrete Ollama-/Treiberkompatibilitaet pruefen. |
| GPU-Zugriff | Bei virtualisiertem Root-Server echtes Passthrough bzw. zugesicherte passende GPU-Zuteilung; Root-Zugriff allein stellt keine GPU bereit. |
| Installation | Native Installation ist moeglich, Docker nicht erforderlich. Ollama unter eigenem unprivilegiertem Servicekonto. |
| Lifecycle | Root-Server als eigenes Deploymentprojekt behandeln; gemeinsamer stackctl-Vertrag statt weiterer Knowledge-Sonderskripte oder konkurrierender Prozessmanager. |
| Verbindung | Von Uberspace aus erreichbarer, dauerhaft ueberwachter SSH-Tunnel oder authentifizierter TLS-Endpunkt. Ein Host-VPN auf Uberspace nicht ungeprueft voraussetzen. |
| API-Schutz | Port 11434 nicht ungeschuetzt ins Internet; Loopback/private Bindung, Firewall, Authentifizierung am Gateway, Anfragelimits und begrenzte Warteschlange. CORS ist keine Zugriffskontrolle. |
| Netzqualitaet | Niedrige stabile RTT zwischen App und Inferenz, als Planungsziel unter 30 ms; keine harte Funktionsvoraussetzung. Streaming und Timeouts ueber die gesamte Verbindung pruefen. |
| Modelldaten | Eigenes persistentes Modellverzeichnis; ausreichend Platz fuer Updates und mehrere Modellvarianten. Modelle und Quantisierung mit Digest dokumentieren. |
| Updates | Ollama-/Treiber-/Modellversionen kontrolliert aktualisieren, vorher Benchmark und Rueckkehrpfad; nicht ungeprueft stets `latest`. |
| Monitoring | RAM/VRAM, GPU-Auslastung, Disk, Warteschlange, Fehler, TTFT und Token-/Embedding-Durchsatz; keine Promptinhalte oder Secrets standardmaessig loggen. |

Chat bleibt hinter `ki_knowledge.llm_provider` / ki-core, Embeddings hinter
dem vorhandenen Ollama-Vertrag. Endpoint und Secrets ueber die bestehende
Konfigurationslinie, nicht dupliziert in Skripten oder `.env`.
Falls ein vorgeschaltetes Gateway neue Authentifizierung erfordert, die
Header-Unterstuetzung beider Clientpfade vorab pruefen und gezielt ergaenzen.
Fuer ausschliesslich eigenen Inferenzbetrieb Cloudfunktionen explizit deaktivieren.

## 5. Abnahme: Was bedeutet hier „flott“?

Vorgeschlagene Zielwerte, **vor Bestellung mit einem Test bestaetigen**:

| Test | Ziel / Messung |
|---|---|
| Warmer Chat, eine Anfrage | Mindestens 20 Ausgabetokens/s, angestrebt 30 oder mehr; separates Testprofil mit etwa 1k Eingabetokens und 256 Ausgabetokens. |
| Erste Ausgabe | p95 unter 3 s bei warmem Modell im selben kurzen Testprofil, einschliesslich App-Netzweg; Streaming erforderlich. |
| Langer Kontext | Repraesentative 8k-/16k-Workloads separat messen; Kurzprompt-Latenz nicht darauf uebertragen. |
| Zwei gleichzeitige Anfragen | Latenz und Durchsatz pro Anfrage erfassen; keine OOMs, keine unbeabsichtigte CPU-Auslagerung im GPU-Profil. |
| Embeddings | Repraesentative Textbloecke mit Laengenverteilung und Batchgroesse messen. Durchsatz muss mindestens die geplante Importmenge im vereinbarten Zeitfenster schaffen. |
| Gemischte Last | Chat waehrend eines begrenzten Imports pruefen; Spitzen-RAM/VRAM, Queue und Fehler erfassen. |
| Betrieb | Dienst-/Tunnelneustart, kaltes Modellladen, Timeouts und kontrollierte Ueberlast testen. |

Pro Messreihe mindestens 30 abgeschlossene Anfragen, Modell-Digest,
Quantisierung, Kontext, Hardware, Parallelitaet, Ollama-Version sowie
Prompt-/Ausgabelaenge festhalten. Streaming-TTFT vom Anfragestart bis zum
ersten Ausgabetoken messen; Token/s aus Ollamas Antwortmetriken berechnen.
Zielwerte dienen der Beschaffung, nicht als ungemessene Hardwareversprechen.

## Quellen

Offizielle Ollama-Dokumentation, gelesen am 03.11.2026:

- [Hardware-/GPU-Unterstuetzung](https://docs.ollama.com/gpu)
- [Betrieb, Modellresidenz und Parallelitaet](https://docs.ollama.com/faq)
- [Kontext und Speicherbedarf](https://docs.ollama.com/context-length)

Hardwareprofile und Abnahmeziele sind Empfehlungen fuer dieses Deployment,
keine vom Ollama-Projekt garantierten Spezifikationen.
