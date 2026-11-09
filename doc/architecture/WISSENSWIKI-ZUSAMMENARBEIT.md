---
project: ki-knowledge
agent_project: ki-knowledge
scope: architecture
created: null
updated: "2026-11-08 19"
update_reason: "Animierte Netzansicht und Kugelidee eingeordnet"
status: draft
semantic_blocks:
  - starting-point
  - shared-work
  - blocks-and-relations
  - local-workspace
  - ordered-composition
  - conversation-and-proposals
  - agent-freedom
  - example
  - open-questions
relations:
  - source: "#shared-work"
    target: "KI-KNOWLEDGE-KONZEPT.md#semantic-working-method"
    type: extends
    reason: "Die gemeinsame Arbeit in Blöcken erhält eine mögliche Arbeitsoberfläche."
  - source: "#blocks-and-relations"
    target: "TEXT-AND-KNOWLEDGE-BLOCKS.md#distinction"
    type: reference
    reason: "Die Unterscheidung von Text- und Wissensblöcken bleibt relevant."
  - source: "#conversation-and-proposals"
    target: "WISSENSWIKI-TECHNIK.md#proposals"
    type: reference
    reason: "Der technische Entwurf beschreibt die mögliche Behandlung von Vorschlägen."
  - target: WISSENSWIKI-TECHNIK.md
    type: reference
    reason: "Technischer Entwurf zur hier beschriebenen Zusammenarbeit"
  - target: README.md
    type: parent
    reason: "Architekturübersicht"
---

# Wissenswiki: Zusammenarbeit

**Gesprächsgrundlage, kein fertiges Produkt:** Der Nutzer hat die Idee eines
einfachen Wikis mit gemeinsamem Schreiben, verlinkten Blöcken, KI-Vorschlägen
und einstellbaren Freiheiten für Agenten eingebracht. Die folgenden
Ausformulierungen sind ein Agentenvorschlag zur gemeinsamen Klärung.

<a id="starting-point"></a>
## Ausgangspunkt [starting-point]

Der lokale Dokumentbetrachter macht Metadaten und Beziehungen sichtbar. Als
reine Leseansicht bietet er gegenüber einem guten Markdown-Betrachter wie
Typora aber noch wenig Mehrwert. Interessanter wäre eine Arbeitsumgebung, in
der aus dem Gespräch heraus Gedanken entstehen, verbunden und weiterentwickelt
werden können.

Der Viewer wurde inzwischen um einen ersten lokalen Arbeitsraum ergänzt.
Gespräch, KI-Vorschläge und Agentenfreiheit unten bleiben weiterhin Ideen.

<a id="shared-work"></a>
## Gemeinsam Gedanken entwickeln [shared-work]

Ein Mensch und eine oder mehrere KI-Instanzen könnten an einem Thema arbeiten:
Gedanken formulieren, Fragen stellen, Unterschiede untersuchen und passende
Zusammenhänge finden. Die Oberfläche soll das gemeinsame Denken unterstützen,
nicht festlegen, was wahr oder wichtig ist.

Das Gespräch wäre nahe bei den Inhalten, auf die es sich bezieht. Nicht jede
Chatnachricht muss ein Block werden: Eine Frage kann im Gespräch bleiben;
ein bewusst ausgewählter Gedanke kann als eigener Block festgehalten werden.

<a id="blocks-and-relations"></a>
## Blöcke und Beziehungen [blocks-and-relations]

Menschen können kurze Blöcke selbst schreiben und miteinander verbinden.
Ein Block kann eine Idee, Frage oder Aussage ausdrücken; Titel und Kategorie
bleiben optional. Beim Verbinden werden Ausgang und Ziel sichtbar; ein
allgemeines „hängt zusammen“ genügt zunächst, wenn keine genauere Bedeutung
festgelegt ist. Eine Beziehung ist eine Einordnung, kein Beweis.

Die hier verwendeten Dokumentationsblöcke sind ein Beispiel für die
Arbeitsweise, nicht automatisch fachliche Wissensblöcke. Woher ein Inhalt
stammt und wer seine Formulierung erzeugt hat, sollte unterscheidbar bleiben;
bei bekannten Quellen auch die konkrete Stelle.

<a id="local-workspace"></a>
## Ein kleiner lokaler Arbeitsraum [local-workspace]

Ein Arbeitsraum kann zunächst ein bewusst begrenzter Ort sein, an dem Gedanken
entstehen und nebeneinander betrachtet werden. Nicht alles muss von Anfang an
einsortiert oder mit einem großen Wissensbestand verbunden sein. Die Nähe
zweier Texte lädt dazu ein, Unterschiede und Zusammenhänge wahrzunehmen.

**Erster Versuch:** Zwei Eingabefelder stehen links und rechts; dazwischen
werden Typ und Richtung einer Beziehung gewählt. Gespeicherte Blöcke sind in
einer einklappbaren, durchsuchbaren Seitenleiste erreichbar und können in
einer gewählten Spalte geöffnet werden. Der Mensch benennt die Beziehung;
die Anwendung behauptet nicht, dass sie fachlich richtig ist. Bei schmalen
Bildschirmen stehen die Bereiche untereinander.

**Idee für später:** Das Wissensnetz könnte auf einer gedachten transparenten
Kugel mit einem Äquatorialnetz sichtbar werden. Wie Positionen, Blickrichtung
und Beziehungen dort entstehen und navigiert werden, ist noch offen; die
heutige Oberfläche stellt keine Kugel oder räumliche Positionen dar.

Eine separate animierte Netzansicht zeigt die eigenen Blöcke als bewegliche
Blasen und ihre gerichteten Beziehungen als farbige Verbindungen. Blöcke
bleiben darin lesbar, aber nicht bearbeitbar; neue Beziehungen können durch
Auswahl zweier Blöcke und eines Typs angelegt werden. Die sieben Typen folgen
dem Graph-Beispiel in `dev_doc`: Dort heißt der allgemeine Verweis
`references`; bisherige `reference`-Beziehungen werden nicht umbenannt.

<a id="ordered-composition"></a>
## Ein längerer Text aus Teilen [ordered-composition]

Ein Essay kann als Ganzes betrachtet werden, das Bestandteile in einer
bestimmten Reihenfolge umfasst. Dieselben Blöcke könnten in einem anderen
Zusammenhang anders angeordnet werden. Die Folge ist eine bewusste
Zusammenstellung; eine Nachbarschaft allein sagt noch nicht, ob ein Gedanke
den nächsten begründet, erweitert oder ihm widerspricht.

**Erster Versuch:** Ein linker Block kann rechte Blöcke als geordnete
Bestandteile aufnehmen. Ihre Reihenfolge lässt sich verändern und ihre Texte
werden in dieser Reihenfolge als Vorschau gezeigt. Ob ein Essay darüber hinaus
Übergänge, Überschriften oder eine eigene Fassung benötigt, bleibt offen.

<a id="conversation-and-proposals"></a>
## Gespräch und Vorschläge [conversation-and-proposals]

Aus Stichworten, einem Titel oder einem kurzen Abriss könnte eine KI einen
Text vorschlagen. Ebenso könnte sie auf Wunsch vorhandene Blöcke vergleichen,
Rückfragen stellen oder mögliche Beziehungen nennen. Der Mensch sieht den
Vorschlag, kann ihn bearbeiten, annehmen oder verwerfen.

Ein angenommener Vorschlag kann zu einem Wissensblock werden. Bis zur
menschlichen Bestätigung bleibt er ein Entwurf; eine KI-Antwort oder ein
Beziehungsvorschlag wird nicht stillschweigend zu bestätigtem Wissen.

<a id="agent-freedom"></a>
## Handlungsspielraum der Agenten [agent-freedom]

Die Dynamik könnte einstellbar sein: von einer Antwort nur auf Anfrage über
gezielte Vorschläge bis hin zu einer begrenzten eigenständigen Erkundung.
Dabei könnten ein oder mehrere Agenten unterschiedliche Perspektiven
beisteuern. Das ist eine Idee für spätere Erprobung, keine Voraussetzung für
den ersten Arbeitsablauf.

Als vorsichtiger Vorschlag bezieht sich größere Freiheit zunächst darauf,
**Entwürfe** selbstständig zu erstellen oder auszubauen. Sie hebt die bisher
vereinbarte menschliche Bestätigung von Wissensblöcken nicht auf. Umfang,
Arbeitsbereich, mögliche Kosten und Abbruch sollen erkennbar und begrenzbar
sein; wie viel Autonomie wir tatsächlich wollen, entscheiden wir gemeinsam.

<a id="example"></a>
## Ein möglicher Ablauf [example]

1. Ein Mensch schreibt „Interne Repräsentation“ als Stichwort und bittet um
   eine kurze Formulierung.
2. Die KI schlägt einen Text vor. Im Gespräch wird er gemeinsam präzisiert.
3. Der Mensch bestätigt die Fassung als Block; die Entstehung der
   Formulierung bleibt erkennbar.
4. Er verbindet den Block mit „Wissensverarbeitungssystem“ als `part-of`.
   Ein späterer Vorschlag für eine weitere Beziehung bleibt zunächst offen.

Das ist ein Beispiel für eine mögliche Bedienung, kein Nachweis einer
Implementierung oder einer automatisch richtigen Beziehung.

<a id="open-questions"></a>
## Offene Fragen [open-questions]

Wie eng sollen Gespräch und Blockbearbeitung zunächst verbunden sein? Soll
ein Agent nach einer ausdrücklichen Aufgabe selbst weitere Entwürfe anlegen
dürfen, und wo liegen dafür sinnvolle Grenzen? Wie unterscheiden wir eigene,
KI-formulierte und gemeinsam überarbeitete Texte, ohne die Arbeit schwerfällig
zu machen? Auch die Wahl der Oberfläche und der Speicherform ist noch offen;
der [technische Entwurf](WISSENSWIKI-TECHNIK.md) untersucht einen kleinen Weg.

**Arbeitsweg, 2026-11-08:** Nutzerideen zur Zusammenarbeit, zu zwei
nebeneinanderstehenden Blöcken und zum Essay als Folge aufgenommen.
Ausgestaltung und Fragen bleiben, soweit nicht als erster Versuch bezeichnet,
Agentenvorschläge und benötigen gemeinsame Prüfung.
