---
project: ki-knowledge
agent_project: ki-knowledge
scope: architecture
created: null
updated: "2026-11-08 16"
update_reason: "Darstellung von Blockrelationen im lokalen Viewer ergänzt"
status: draft
semantic_blocks:
  - purpose
  - knowledge-core
  - internal-representation
  - intake
  - work-and-review
  - relations-and-context
  - discovery-and-output
  - existing-system
  - next-decisions
  - semantic-working-method
  - component-relations
  - documentation-relations
relations:
  - source: "#internal-representation"
    target: "#purpose"
    type: part-of
    reason: "Die interne Repräsentation ist Teil des beschriebenen Wissensverarbeitungssystems."
  - source: "#purpose"
    target: "#internal-representation"
    type: composed-of
    reason: "Das beschriebene System umfasst unter anderem die interne Repräsentation."
  - target: README.md
    type: parent
    reason: "Architekturübersicht"
  - target: ../README.md
    type: reference
    reason: "Dokumentationseinstieg"
  - target: SYSTEM_OVERVIEW.md
    type: reference
    reason: "Bisherige Produktrichtung und historischer Systemüberblick"
  - target: TEXT-AND-KNOWLEDGE-BLOCKS.md
    type: reference
    reason: "Wissensblockbegriff, Beispiele und offene Vorschläge"
  - target: SOURCE-WORKSPACE-AND-WORKFLOW-CONCEPT.md
    type: reference
    reason: "Bestehender Quellenaufnahme- und Vorbereitungsprozess"
  - target: KNOWLEDGE-WORKBENCH-CONCEPT.md
    type: reference
    reason: "Textwerkstattentwurf und Abgrenzung der bisherigen Arbeitsweise"
  - target: ../features/knowledge_retrieval.md
    type: reference
    reason: "Einordnung vorhandener und gewünschter Retrievalfunktionen"
  - target: ../guides/text-workbench.md
    type: reference
    reason: "Bedienung der bestehenden Textwerkstatt"
  - target: ../features/knowledge_presentation_requirements.md
    type: reference
    reason: "Historischer Ausgabeentwurf, nicht die aktuelle Produktgrenze"
---

# Ki-Knowledge: fachliches Konzept

Dieser Entwurf verbindet die gemeinsam erarbeitete Produktrichtung mit
ausgewählten vorhandenen Arbeitswegen. **Zielbild, Vorschläge und bestehende
Umsetzung sind nicht gleichzusetzen.** Technische Entscheidungen und Migrationen
werden hier nicht vorweggenommen.

<a id="purpose"></a>
## Zweck [purpose]

Ki-Knowledge soll einen eigenständigen Umgang mit Wissen ermöglichen: Inhalte
aus verschiedenen Quellen aufnehmen, Wissensblöcke bearbeiten, miteinander
verbinden, wiederfinden und für neue Inhalte verwenden. Menschen und KI können
bei der Arbeit zusammenwirken; sinnvolle Voreinstellungen sollen den Einstieg
ermöglichen, ohne sämtliche Metadaten oder Beziehungen vorab festzulegen.

Der Wissenskern soll erweiterbar bleiben, auch für komplexere
Wissenstechnologien. Eingabe, Domänen und Ausgabe gehören zum Produkt; keine
bestimmte Quelldatei oder einzelne Ausgabeform definiert den gesamten Kern.

<a id="knowledge-core"></a>
## Wissenskern [knowledge-core]

Ein Textblock ist zunächst eine zusammenhängende Textfolge. Ein Wissensblock
ist davon fachlich getrennt: Er wird nach Bedeutung betrachtet und hat eine
Textrepräsentation. Beide müssen nicht dieselben Grenzen oder denselben
Wortlaut haben.

Wissensblöcke können aus einer Quelle stammen, selbst verfasst oder mit einem
LLM vorgeschlagen werden. Jeder benötigt Herkunftsinformation; Inhaltsquelle
und Entstehung der Formulierung werden getrennt betrachtet. Ist bei einem
quellenbasierten Block die konkrete Textstelle bekannt, wird sie hinterlegt.
Titel und Kategorie sind optional. Ein LLM-Vorschlag wird erst nach
menschlicher Bestätigung als Wissensblock übernommen.

Die [Begriffe, Beispiele und offenen Details](TEXT-AND-KNOWLEDGE-BLOCKS.md)
werden dort weitergeführt. Insbesondere sind das genaue Herkunftsschema und
der technische Bezug zu Quellen noch nicht entschieden.

<a id="internal-representation"></a>
## Interne Repräsentation [internal-representation]

**Vorschlag:** Die interne Repräsentation ist die Form, in der
ki-knowledge Wissen für die weitere Arbeit verfügbar hält. Zu ihr gehören
die [Wissensblöcke](#knowledge-core), ihre Herkunft und
[Beziehungen](#relations-and-context) zueinander.

Sie ist von einer einzelnen Eingabequelle und einer bestimmten Ausgabeform
zu unterscheiden. Welche weiteren Dinge intern repräsentiert werden und wie
sie technisch gespeichert werden, ist noch offen.

<a id="intake"></a>
## Quellen und Aufnahme [intake]

Quellen können verschiedene Formate und Herkunftssysteme haben. Eine
formatbasierte Gliederung, beispielsweise eines EPUB, kann Ausgangspunkt für
die spätere semantische Arbeit sein; sie ist noch keine semantische Erfassung.
Jira soll künftig ein gleichberechtigtes Eingabe-/Importformat sein; die
vorhandenen Jira-Sonderpfade sind Legacy, ihre Ablösung ist noch nicht belegt.

Der bestehende [Aufnahmeprozess](SOURCE-WORKSPACE-AND-WORKFLOW-CONCEPT.md)
unterscheidet Auffinden, Prüfen, Vorbereiten und expliziten Import. Import,
semantische Bearbeitung, Prüfung und Veröffentlichung sind unterschiedliche
Schritte. Ein Importstatus allein besagt nicht, dass Wissen verstanden oder
freigegeben wurde.

<a id="work-and-review"></a>
## Bearbeiten und prüfen [work-and-review]

Menschen können Text und Wissen bearbeiten und KI-Vorschläge prüfen. Für
quellenbasierte Arbeit soll die Herkunft nachvollziehbar bleiben; ein
Wissensblock muss aber nicht an eine Datei oder Textrevision gebunden sein.
Das Zusammenspiel von Bearbeitung, früheren Fassungen und Quellbezügen ist
als [Vorschlag](TEXT-AND-KNOWLEDGE-BLOCKS.md#change-proposal) beschrieben.

Die vorhandene [Textwerkstatt](../guides/text-workbench.md) ermöglicht Arbeit
mit Textrevisionen und Markierungen. Sie ist ein Prototyp und kein Nachweis,
dass das hier beschriebene eigenständige Wissensblockmodell bereits umgesetzt
ist. Der [Werkstattentwurf](KNOWLEDGE-WORKBENCH-CONCEPT.md) enthält weitere
Ideen, die gegen dieses Modell neu zu prüfen sind.

<a id="relations-and-context"></a>
## Beziehungen und Kontext [relations-and-context]

Wissensblöcke sollen miteinander verbunden werden können. Eine allgemeine
Beziehung „hängt zusammen“ ist möglich; genauere Beziehungstypen und ihre
Bedeutung sind noch offen. Eine Beziehung ist eine Einordnung, kein Beweis.

Domänen können den Arbeitskontext für Quellen und Wissen bilden. Die Rolle
von Mehrfachzuordnungen, domänenübergreifenden Beziehungen und Zugriffsrechten
ist noch zu klären. Die vorhandene Domain-Registry vereinheitlicht nicht
automatisch die verschiedenen Speicher.

<a id="discovery-and-output"></a>
## Finden und Ausgeben [discovery-and-output]

Suche, Retrieval und Chat bleiben gewünschte Funktionen. Ein Vorschlag für
den Einstieg ist die Textsuche nach Wissensblöcken mit erkennbarer Herkunft;
semantische Suche und weitere Verfahren benötigen eine eigene Ausarbeitung.
Treffer sind keine Wahrheitsgarantie. Die
[Retrieval-Übersicht](../features/knowledge_retrieval.md) grenzt vorhandenen
Domain-Chat und Jira-Altpfade vom neuen Zielbild ab.

Wissensblöcke könnten für Notizen, Übersichten oder andere Ausgaben ausgewählt
und angeordnet werden. Eine Ausgabe muss nicht der Quellgliederung folgen.
Formate, Quellenanzeige und Freigabe sind noch offen; Speichern und
Veröffentlichen sind unterschiedliche Schritte.
Ein [früherer Ausgabeentwurf](../features/knowledge_presentation_requirements.md)
ist für die weitere Prüfung erhalten; seine damaligen Einschränkungen sind
keine Vorgaben für das neue Wissensmodell.

<a id="existing-system"></a>
## Bestehendes System und Grenzen [existing-system]

Heute bestehen unter anderem Quelleninventar und Importwege, Parser und
KnowledgeStore-Records, die Textwerkstatt sowie ein separater Domain-Chat.
Ihre konkreten Grenzen stehen in den jeweiligen Anleitungen und
Bestandsaufnahmen. Ein vorhandener `KnowledgeBlockRecord`, eine
Werkstattmarkierung und der neue fachliche Wissensblock sind nicht
automatisch dasselbe Objekt.

InfoSite Import Control führt derzeit eine synchrone Statusübergabe aus,
keine Inhaltsaufnahme oder semantische Extraktion; siehe
[InfoSite](../features/INFOSITE.md#import-control-current-execution-contract).
Der ältere [Systemüberblick](SYSTEM_OVERVIEW.md) enthält daneben historische
und ungeprüfte Aussagen und ist nicht insgesamt als aktuelle Architektur zu
lesen.

<a id="next-decisions"></a>
## Weiterer Arbeitsstand [next-decisions]

Als nächste fachliche Vertiefung bieten sich Herkunft bei Überarbeitungen,
Beziehungstypen und Domänengrenzen an. Der beispielhafte
[Arbeitsweg](TEXT-AND-KNOWLEDGE-BLOCKS.md#example-workflow) verbindet diese
Fragen mit Suche und Ausgabe; er behauptet keine fertige Implementierung.

**Arbeitsweg, 2026-11-08:** Gemeinsame Entscheidungen aus der
Produktrichtung und dem Wissensblockkonzept wurden mit Quellenaufnahme,
Werkstatt und Retrieval abgeglichen. Nicht bestätigte Annahmen bleiben als
Vorschläge kenntlich; getrennte Stores und Jira-Legacy wurden nicht zu einer
bereits existierenden einheitlichen Pipeline erklärt.

<a id="semantic-working-method"></a>
## Gemeinsam in Blöcken arbeiten [semantic-working-method]

**Gemeinsam bestätigt, 2026-11-08:** Wir beschreiben ki-knowledge gemeinsam
in kleinen, in sich verständlichen Textblöcken. Jeder Block behandelt einen
Gedanken, hat eine stabile ID und kann mit anderen Blöcken in Beziehung stehen.
Wir suchen zuerst nach vorhandenen passenden Blöcken, prüfen ihren Inhalt und
ergänzen oder korrigieren sie gemeinsam. Neue Blöcke entstehen dort, wo noch
etwas fehlt; Vorschläge bleiben erkennbar, bis wir sie geklärt haben.

So erproben wir die Wissensarbeit zunächst selbst: Wir zerlegen ein Thema,
verbinden die Teile und lernen dabei, welche Unterstützung die Anwendung
später auf höherem Niveau leisten könnte. Dokumentationsblöcke sind dabei
nicht automatisch bereits implementierte fachliche Wissensblöcke.

<a id="component-relations"></a>
## Erster Zusammenhang: das System [component-relations]

**Bestätigter Ausgangspunkt:** Der [Zweck](#purpose) beschreibt
ki-knowledge als Wissensverarbeitungssystem. Dazu gehören die
[Quellen und Aufnahme](#intake), die
[interne Repräsentation](#internal-representation) und das
[Finden und Ausgeben](#discovery-and-output).

Diese Zuordnung ist ein erster Vorschlag; sie legt noch keine fertige
technische Architektur oder zwingende Reihenfolge fest. Welche weiteren
Komponenten und Beziehungen nötig sind, können wir nach und nach gemeinsam
herausarbeiten.

<a id="documentation-relations"></a>
## Beziehungen zwischen Dokumentationsblöcken [documentation-relations]

**Diskussionsgrundlage, 2026-11-08:** Die gemeinsamen
[Grundlagen](../../../../dev_doc/documentation-guidelines/SEMANTIC_KNOWLEDGE_ORGANIZATION.md)
und das [Graph-Beispiel](../../../../dev_doc/documentation-guidelines/DOCUMENTATION_VISUALIZATION.md#graph-visualization-graph-generation)
nennen verschiedene Relationstypen. Eine Relation hat eine Richtung: Die
folgende Bedeutung ist jeweils von **A nach B** zu lesen.

| Typ | Bedeutung von A → B |
|---|---|
| `part-of` | A ist Teil von B. **Gemeinsam bestätigt.** |
| `composed-of` | A setzt sich aus B zusammen; weitere Teile können hinzukommen. **Vorläufig gemeinsam angenommen.** |
| `depends-on` | A benötigt B als Voraussetzung zum Verständnis. |
| `extends` | A baut auf B auf oder erweitert B. |
| `implements` | A beschreibt die Umsetzung des in B beschriebenen Entwurfs. |
| `reference` / `references` | A verweist auf B, ohne eine stärkere Beziehung zu behaupten. |
| `deprecates` | A kennzeichnet B als überholt; ob A B auch ersetzt, ist noch zu klären. |

`part-of` und `composed-of` beschreiben vorläufig denselben
Teil-Ganzes-Zusammenhang aus entgegengesetzten Richtungen. Eine genauere
Unterscheidung können wir später ergänzen. Nicht jede Erweiterung ist zugleich
eine Voraussetzung. Der allgemeine Verweis sagt zunächst nur, dass ein Bezug
besteht.

**Bestätigtes Beispiel:** Die interne Repräsentation `part-of` das
Wissensverarbeitungssystem. Der Block
[`internal-representation`](#internal-representation) beschreibt den Teil;
der [Zweck](#purpose) beschreibt das System. Im YAML-Header ist die Beziehung
in beiden Richtungen notiert: Das Wissensverarbeitungssystem `composed-of`
unter anderem die interne Repräsentation.

Für unsere Dokumentation verwenden wir bisher `reference` im YAML; das
gemeinsame Graph-Beispiel nennt `references`. Die gemeinsame Grundlage ist
ein Entwurf und führt `replaces` separat an, während das Graph-Beispiel
`deprecates` als Ersetzung beschreibt. Schreibweisen und die genaue Grenze
zwischen Veralten und Ersetzen wollen wir gemeinsam klären, statt sie hier
stillschweigend festzulegen.

**Darstellung:** `semantic_blocks` listet die Abschnitts-IDs. Bei den beiden
Beispielrelationen oben im YAML benennt `source` den Ausgangsblock und
`target` den Zielblock, jeweils als lokales Fragment; `type` gibt die Richtung
und Art der Beziehung an. Die meisten bisherigen YAML-Relationen ohne
`source` beziehen sich dagegen auf das Dokument. Das zusätzliche `source`
ist eine erste Notation für Blockbeziehungen; der lokale Dokumentbetrachter
zeigt sie als ausgehende Beziehungen an. Ein Markdown-Link allein benennt
noch keinen Relationstyp. Dies betrifft unsere Dokumentation und entscheidet
nicht automatisch über Relationstypen im späteren Wissensmodell.
