---
project: ki-knowledge
agent_project: ki-knowledge
scope: architecture
created: null
updated: "2026-11-08 10"
update_reason: "Inhaltlichen Bezug der beiden Beispiele als Verweis festgehalten"
status: draft
semantic_blocks:
  - distinction
  - practical-example
  - relation-example
  - relation-proposal
  - change-proposal
  - domain-proposal
  - search-proposal
  - output-proposal
  - example-workflow
  - open-questions
relations:
  - source: "#relation-example"
    target: "#practical-example"
    type: reference
    reason: "Das Beziehungsbeispiel greift das EPUB-Beispiel und dessen Thema auf."
  - source: "#practical-example"
    target: "#distinction"
    type: depends-on
    reason: "Das Beispiel setzt die Unterscheidung von Text- und Wissensblock voraus."
  - source: "#distinction"
    target: "KI-KNOWLEDGE-KONZEPT.md#knowledge-core"
    type: extends
    reason: "Die Unterscheidung von Text- und Wissensblöcken vertieft den Wissenskern."
  - target: README.md
    type: parent
    reason: "Architekturübersicht"
  - target: SYSTEM_OVERVIEW.md
    type: reference
    reason: "Gemeinsam erarbeitete Produktrichtung"
  - target: KI-KNOWLEDGE-KONZEPT.md
    type: reference
    reason: "Fachlicher Gesamtentwurf und Einordnung des Wissenskerns"
  - target: KNOWLEDGE-WORKBENCH-CONCEPT.md
    type: reference
    reason: "Älterer Entwurf für Annotationen, Relationen und Überarbeitungen"
  - target: CONTENT-MODEL-MATRIX.md
    type: reference
    reason: "Bestandsaufnahme der Domain-Registry und getrennter Speicher"
  - target: SOURCE-WORKSPACE-AND-WORKFLOW-CONCEPT.md
    type: reference
    reason: "Bisherige Trennung von Quellenaufnahme und Ausgabe"
  - target: ../features/knowledge_retrieval.md
    type: reference
    reason: "Einordnung vorhandener Retrieval-Pfade und Jira-Legacy"
  - target: ../features/knowledge-workbench-design.md
    type: reference
    reason: "Wireframes für Werkstattmarkierungen, nicht das neue Wissensblockmodell"
---

# Text- und Wissensblöcke

Dieses Konzept vertieft den Wissenskern des
[fachlichen Gesamtentwurfs](KI-KNOWLEDGE-KONZEPT.md). Es beschreibt die
gemeinsam entwickelte Vorstellung, nicht ein bereits umgesetztes Datenmodell.

<a id="distinction"></a>
<a id="unterscheidung-distinction"></a>
## Textblock und Wissensblock unterscheiden [distinction]

Ein **Textblock** ist eine zusammenhängende Folge von Zeichen oder Wörtern.
Er kann beispielsweise anhand der Formatierung oder Struktur einer Quelle
abgegrenzt werden; das allein erfasst noch keine Bedeutung.

Ein **Wissensblock** wird fachlich und semantisch betrachtet und hat eine
Repräsentation als Text. Er ist getrennt von Textblöcken zu betrachten, nicht
als etwas, das ein Textblock notwendigerweise enthält. Seine Textrepräsentation
kann zufällig einer Textpassage entsprechen; sie kann bei der semantischen
Erfassung aber auch anders abgegrenzt oder formuliert werden.

Wissensblöcke können aus Quellen stammen, selbst verfasst oder mit einem LLM
erzeugt werden. Jeder Wissensblock braucht Herkunftsinformation, mindestens
die Entstehungsart. Dabei werden die Quelle des Inhalts und die Entstehung
seiner Formulierung getrennt betrachtet: Eine Aussage kann sich etwa auf ein
EPUB beziehen und zugleich von einem LLM formuliert worden sein. Eine
Quelldatei oder Textrevision ist nicht immer nötig.
Entsteht ein Wissensblock aus einer Quelle, wird die konkrete Textstelle
hinterlegt, sofern sie bekannt ist.

Ein LLM-Vorschlag wird erst nach menschlicher Bestätigung als Wissensblock
übernommen. Wie Vorschläge bis dahin gespeichert und geprüft werden, ist offen.
Eine Kategorie wie „Aussage“, „Frage“ oder „Idee“ und ein eigener Titel sind
optional; ein Wissensblock kann zunächst ohne beides angelegt werden.

<a id="practical-example"></a>
## Praktisches Beispiel [practical-example]

Ein importierter Absatz kann als Textblock erfasst werden. Bei der späteren
semantischen Bearbeitung wird überlegt, welche Wissensblöcke daraus entstehen
sollen und wie deren Textrepräsentationen lauten. Die Abgrenzung des Absatzes
ist dabei ein Ausgangspunkt, keine Vorschrift für die Wissensblöcke.

Für den ersten Vortrag des importierten EPUB *GA193* wurde beispielsweise
folgende Textrepräsentation vorgeschlagen: „Der Vortrag beschreibt Hochmut
und Bescheidenheit als ein Spannungsfeld menschlicher Selbsteinschätzung.“
Sie fasst eine Passage sinngemäß zusammen und ist kein Originalzitat. Die
Quelle des Inhalts ist der EPUB-Import; die Formulierung entstand als
LLM-Vorschlag und wurde vom Menschen als Beispielrichtung bestätigt. Das
Beispiel ist kein gespeicherter Wissensblock und keine Aussage über die
heutige Umsetzung.

<a id="relation-example"></a>
## Beispiel für eine Beziehung [relation-example]

Zum EPUB-Beispiel könnte ein zweiter, eigenständig formulierter Wissensblock
hinzukommen: „Wie kann man Selbstvertrauen und Bescheidenheit miteinander
vereinbaren?“ Er wäre eine Frage, keine Aussage des Buches; seine Formulierung
ist hier lediglich ein Beispielvorschlag.

Eine mögliche Beziehung wäre: Die Frage **greift das Thema auf**, das der
erste Block anhand des Vortrags beschreibt. Die Beziehung selbst wäre eine
Einordnung, kein Beweis und keine Behauptung, dass das Buch die Frage so
formuliert. Beide Blöcke und die Beziehung sind Beispiele, nicht gespeichert.

Eine allgemeine Beziehung wie „hängt zusammen“ soll möglich sein, auch wenn
kein genauerer Beziehungstyp angegeben wird. Weitere Beziehungstypen und ihre
Bedeutung sind noch offen.

Der ältere Textwerkstattentwurf schlägt bereits
[Relationstypen für Annotationen](KNOWLEDGE-WORKBENCH-CONCEPT.md#11-metadaten-und-relationen-metadata-and-relations)
vor. Ob und wie diese für das neue Wissensmodell passen, ist noch zu prüfen.
Auch die „Blöcke“ im zugehörigen
[Editor-Wireframe](../features/knowledge-workbench-design.md) bezeichnen
Werkstattmarkierungen, nicht automatisch fachliche Wissensblöcke.

Die folgenden fünf Abschnitte sind **eigenständig erarbeitete Vorschläge**
für die weitere Diskussion, keine bestätigten Entscheidungen und kein
Nachweis einer Implementierung.

<a id="relation-proposal"></a>
## Beziehungen [relation-proposal]

- Die vereinbarte allgemeine Beziehung „hängt zusammen“ genügt für den
  Einstieg. Genauere Bedeutungen wie „stützt“ oder „widerspricht“ können
  später ergänzt werden; eine Beziehung ist immer eine Einordnung, kein Beweis.
- Menschen können Beziehungen bewusst anlegen. Ein LLM könnte Beziehungen
  vorschlagen; ob und wie solche Vorschläge bestätigt werden müssen, ist offen.
- Als Vorschlag soll eine Beziehung die verbundenen Wissensblöcke und ihre
  Bedeutung erkennbar machen. Eine optionale Begründung könnte helfen, die
  Einordnung später nachzuvollziehen.

Der Werkstattentwurf behandelt Relationen zwischen Annotationen derselben
Domain. Das ist ein Anhaltspunkt, aber weder eine Entscheidung über
domainübergreifende Wissensbeziehungen noch ein fertiges Wissensblockmodell.

<a id="change-proposal"></a>
## Änderungen und Nachvollziehbarkeit [change-proposal]

- Ein Wissensblock soll überarbeitet werden können, ohne seine Quelle zu
  verändern. Frühere Fassungen und die Herkunft der jeweiligen Formulierung
  sollten nachvollziehbar bleiben; die konkrete Versionierung ist offen.
- Bei einer inhaltlichen Änderung sollten Quellenbezüge und Beziehungen
  überprüft werden können, statt sie stillschweigend als weiterhin zutreffend
  auszugeben. Wie Prüfbedarf erkannt und dargestellt wird, ist offen.
- Eine spätere Änderung einer Quelle soll einen gespeicherten Block nicht
  automatisch verändern. Die bisherige Quellstelle sollte weiterhin erkennbar
  bleiben; ist sie nicht mehr auffindbar, soll das sichtbar sein.

Der bestehende Werkstattpfad behandelt
[Textrevisionen und historische Markierungen](../guides/text-workbench.md#text-revisions).
Er ist ein nützlicher Vergleich, aber noch kein Revisionsmechanismus für
Wissensblöcke.

<a id="domain-proposal"></a>
## Domänen [domain-proposal]

- Eine Domäne kann als Arbeitskontext dienen, in dem Quellen, Wissensblöcke
  und ihre Beziehungen gemeinsam betrachtet werden.
- Für einen ersten Arbeitsablauf könnte die aktive Domäne den Such- und
  Bearbeitungskontext vorgeben, ohne dass damit eine fachliche Wahrheit oder
  eine unveränderliche Zugehörigkeit festgelegt wird.
- Ob ein Block mehreren Domänen zugeordnet werden kann und ob Beziehungen
  Domänengrenzen überschreiten dürfen, bleibt offen. Ebenso ist die
  Berechtigung dafür gesondert zu klären; eine Domäne allein ist keine
  Aussage über Zugriffsrechte.

Die [Domain-Registry](CONTENT-MODEL-MATRIX.md) beschreibt eine bestehende
gemeinsame Klammer bei weiterhin getrennten Speichern. Daraus folgt noch keine
einheitliche Speicherung oder fachliche Zuordnung für das neue Modell.

<a id="search-proposal"></a>
## Suche und Retrieval [search-proposal]

- Ein erster Nutzen wäre, Wissensblöcke anhand ihrer Textrepräsentation zu
  finden und Herkunft sowie bekannte Quellstelle beim Ergebnis anzuzeigen.
  Kategorie und Titel dürfen fehlen; die Suche soll sie nicht voraussetzen.
- Quellen bzw. Textblöcke und Wissensblöcke sollten als unterschiedliche
  Ergebnisarten erkennbar bleiben. Ein Treffer oder Ähnlichkeitswert bestätigt
  weder die Wahrheit einer Aussage noch die Richtigkeit ihrer Herkunft.
- Als Einstieg bietet sich eine einfache Textsuche im gewählten Kontext an.
  Semantische Suche, Graphsuche und Chat können darauf aufbauen; Verfahren,
  Abdeckung und Umgang mit nicht indexierten Inhalten sind noch zu bestimmen.

Die [Retrieval-Übersicht](../features/knowledge_retrieval.md) grenzt
Jira-spezifische Legacy-Pfade vom separaten Domain-Chat ab. Keiner dieser
Pfade belegt bereits eine quellenübergreifende Suche im neuen Wissensmodell.

<a id="output-proposal"></a>
## Ausgabe [output-proposal]

- Wissensblöcke könnten für eine Ausgabe ausgewählt und angeordnet werden,
  beispielsweise für eine Notiz oder eine thematische Übersicht. Eine
  Ausgabeordnung muss nicht der Struktur der Eingabequelle entsprechen.
- Quellbezüge und Beiträge zur Formulierung sollten bei der Erstellung
  nachvollziehbar bleiben. Ob und wie sie in einer konkreten Ausgabe sichtbar
  sind, hängt von deren Zweck ab und ist noch zu entscheiden.
- Eine KI könnte Entwürfe für eine Ausgabe vorschlagen. Speicherung eines
  Wissensblocks und Veröffentlichung einer Ausgabe sind getrennte Schritte;
  Freigabe und Ausgabeformate sind noch nicht festgelegt.

Der bestehende [Quellen- und Ausgabeprozess](SOURCE-WORKSPACE-AND-WORKFLOW-CONCEPT.md)
unterscheidet Aufnahme und Veröffentlichung. Eine ältere
[Präsentationsanforderung](../features/knowledge_presentation_requirements.md)
schloss Wissensblöcke zunächst aus; diese historische Scope-Grenze ist keine
Festlegung für die neue Ausgabeplanung.

<a id="example-workflow"></a>
## Beispielhafter Arbeitsweg [example-workflow]

Als zusammenhängender Vorschlag für das EPUB-Beispiel:

1. In der gewählten Domäne die Quelle öffnen und eine bekannte Textstelle
   auswählen; das Original bleibt unverändert.
2. Eine sinngemäße Textrepräsentation formulieren oder von einem LLM
   vorschlagen lassen. Inhaltliche Quelle und Entstehung der Formulierung
   getrennt festhalten; einen LLM-Vorschlag erst nach Bestätigung übernehmen.
3. Optional eine eigene Frage als weiteren Wissensblock formulieren und
   beide über „hängt zusammen“ verbinden. Die Frage wird nicht als
   ursprüngliche Aussage des Buches ausgegeben.
4. Die Blöcke über ihren Text wiederfinden und bei Bedarf für eine Übersicht
   auswählen. Suchergebnis und Übersicht lassen den Bezug zur Quelle erkennen.
5. Wird ein Block überarbeitet oder die Quelle verändert, die bisherigen
   Herkunftsangaben und die Beziehung auf weitere Gültigkeit prüfen.

Dieser Ablauf illustriert das Zielbild; er setzt keine bereits verfügbare
Speicherung, Suche oder Ausgabe voraus.

<a id="open-questions"></a>
## Offene Fragen [open-questions]

Wie ein Verweis auf eine Textstelle technisch dargestellt und bei Änderungen
erhalten wird, ist noch nicht entschieden. Ebenso offen ist, ob und wie die
Erfassungsart – etwa formatbasiert oder semantisch – als Attribut festgehalten
wird und wie sie sich von der Herkunftsinformation abgrenzt.

Die fünf Vorschläge sind noch fachlich zu prüfen. Insbesondere fehlen
Entscheidungen zu weiteren Beziehungstypen, Revisions- und Quellverweisen,
Domainzuordnung und -rechten, Suchabdeckung sowie Freigabe und Ausgabeformaten.
Vorhandene Dokumentblöcke dienen als Ausgangspunkt, nicht automatisch als
gültiges Zielmodell.

**Arbeitsweg, 2026-11-08:** Die Blöcke zu Werkstattrelationen und
-revisionen, Domain-Registry, Retrieval sowie Quellen und Ausgabe wurden mit
dem gemeinsam erarbeiteten Wissensblockbegriff verglichen. Die Abschnitte oben
halten daraus abgeleitete Agentenvorschläge fest; die älteren Implementierungen
und Jira-Beispiele wurden nicht als Beleg für das neue Modell übernommen.
