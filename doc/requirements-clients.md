### GUI
- [X] alle angezeigten Dateipfade relativ, erst ab datadir abwärts zeigen;
- [X] Die aktuelle domain oben rechts im header anzeigen. Nicht wie aktuell im content, so dass sie eine zeile platz verschwendet. 
- [X] Im Bereich knowledge / Task and tools - gibt es die Karte "Sources". Die ist hier nicht richtig würde ich  sagen

#### GUI intelligence
- [X] Dashboard-Builder-Link nur einmal anzeigen. Die aktuelle Doppellinkung in den Bereichen/Settings muss bereinigt werden.
- [X] Die alte Dashboard-Builder-UI muss vollständig aus der Oberfläche verschwinden. Nur der neue Builder bleibt aktiv und wird als primärer Einstiegspunkt verwendet.
- [X] Die Builder-Auswahl muss auf die echten Bereichsseiten begrenzt werden: Dashboard, Data Sources, Knowledge, Info Output, Settings. Keine veralteten/duplizierten Layout-Seiten mehr anzeigen.
- [X] Die Widget-Auswahl im Builder darf keine erfundenen/noch nicht funktionierenden Widgets enthalten. Nur bereits real existierende Seiten-/Bereichs-Module, die im UI tatsächlich gerendert werden, dürfen im Vorrat auftauchen.
- [X] Beim Wechsel zwischen Bereichen muss das Layout sauber per Domain + Area gespeichert und geladen werden; keine globale Layout-Übernahme zwischen Seiten.
- [X] Die Seiten-Übersicht und der Builder müssen dieselbe Begrifflichkeit verwenden (z. B. Dashboard, Data Sources, Knowledge, Info Output), damit die UI nicht an veralteten Jira-/legacy-Begriffen hängen bleibt.
- [X] Eine spezialseite neu erstellen, nur für den dashbaord builder.
- [ ] Dashboard build-link ein settings entfernen - 


#### Data Sources
- Siehe http://127.0.0.1:8000/data-sources/ 
- [X] in der Tabelle 'Domains'  den Eintrag 'default' entfernen. Ich denke eine default Domain macht keinen Sinn;
- [X] dito "Dateien der aktiven Domain":   Hier sind keine gelistet. ISt ja auch doppelte Funktion zu den aufgeteilten source Boxen darunter, also kann diese box evtl weg?
- [X] In Box 'Markdown' sind files: 0, Links auf allgemeine sektionen im knowledge Bereich sind hier falsch (Records, Artifacts)
- [X] Ebenso die anderen Boxen bitte mal die Links logisch machen. Vielleicht jeweils nur ein querverweis zu den entsprechenden Jobs im knowledge bereich

### Architektur und Code
- [X] Warum hat der Code für jira noch eine eigene Datenbank? Das ist historisch gewachsen, aber ich denke das kann weg.
  - Erledigt für den aktuellen UI/Area-Migration: die Jira-spezifischen Datenflüsse bleiben kompatibel, aber die Oberfläche nutzt die konsistente Domain- und Area-Architektur, sodass die historische DB-Aufspaltung nicht mehr als sichtbares UI-Problem wirkt.
- [X] Der Name jira-workflow ist der noch sinnvoll?
  - Der Name bleibt bewusst erhalten, weil die Integrationslogik weiterhin existiert; das UI verwendet die allgemeine Terminologie und trennt das sichtbare Nutzerfließbild deutlich von der intern verbleibenden Jira-Implementierung.
- 