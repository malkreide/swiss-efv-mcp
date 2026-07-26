# Use Cases & Examples — swiss-efv-mcp

Realitätsnahe Anfragen nach Zielgruppe. Der Server erschliesst den Bundeshaushalt der Eidgenössischen Finanzverwaltung (EFV): Einnahmen, Ausgaben, Saldo, Schuldenquoten (mit Prognosen bis 2029), hierarchische Budget-Aufschlüsselung und Ausgaben nach Departement. **API-Key nötig: Nein** — die EFV-Daten stammen aus öffentlichen OGD-Dumps (opendata.swiss) und erfordern keine Authentifizierung.

> Tipp: `fiscal_list_dimensions` zuerst aufrufen — es liefert die gültigen Parameterwerte (Variablen, Haushalte, Modelle, Budget-Themen, Departemente), aus denen sich korrekte Argumente bauen lassen.

## 🏫 Bildung & Schule

**«Wie viel gibt der Bund für das Aufgabengebiet Bildung/Forschung aus, und wie hat es sich entwickelt?»**
- **API-Key nötig:** Nein
- → `fiscal_list_dimensions()`
- → `fiscal_budget_breakdown(topic="Ausgaben nach Aufgabengebiet", level=2)`
- Warum nützlich: Zeigt anschaulich, welche Aufgabengebiete welchen Anteil am Bundeshaushalt haben — eine konkrete Grundlage für Unterricht zu Staatsfinanzen und politischer Bildung.

**«Wie unterscheiden sich Einnahmen und Ausgaben des Bundes über die Zeit?»**
- **API-Key nötig:** Nein
- → `fiscal_headline(variable="einnahmen", household="bund", year_from=2010)`
- → `fiscal_headline(variable="ausgaben", household="bund", year_from=2010)`
- Warum nützlich: Jeder Punkt trägt `is_projection`, sodass Ist-Werte und Budget-/Planjahre im Schulmaterial klar getrennt bleiben.

**«Wie hoch ist die Bruttoschuldenquote des Bundes — und wohin geht die Prognose?»**
- **API-Key nötig:** Nein
- → `fiscal_headline(variable="bruttoschuldenquote", household="bund", year_from=2000, year_to=2029)`
- Warum nützlich: Verbindet historische Werte mit Prognosen bis 2029 in einer Reihe — geeignet, um die «Schuldenbremse» greifbar zu machen.

## 👨‍👩‍👧 Eltern & Schulgemeinde

**«Welchen Anteil des Bundeshaushalts machen einzelne Ausgabenarten aus?»**
- **API-Key nötig:** Nein
- → `fiscal_budget_breakdown(topic="Ausgaben nach Art", level=2)`
- Warum nützlich: Macht für interessierte Bürger:innen und Eltern nachvollziehbar, wohin Steuergeld fliesst — ohne Fachwissen über Rechnungsmodelle.

**«Wie viel gibt ein bestimmtes Departement für Personal oder Informatik aus?»**
- **API-Key nötig:** Nein
- → `fiscal_list_dimensions()`
- → `fiscal_by_institution(departement="<Departement>", variable="Personalausgaben", year_from=2015)`
- Warum nützlich: Bringt Transparenz über Verwaltungsausgaben seit 2007 (Personal, Informatik, externe Dienstleistungen, Vollzeitstellen) auf eine konkrete Verwaltungseinheit herunter.

## 🗳️ Bevölkerung & öffentliches Interesse

**«Wie hat sich der Bundessaldo seit der SNB-Zinswende 2022 entwickelt?»**
- **API-Key nötig:** Nein
- → `fiscal_headline(variable="saldo", household="bund", year_from=2021)`
- Warum nützlich: Beantwortet eine typische Medien- und Politikfrage direkt mit amtlichen Zahlen — inklusive der Kennzeichnung, welche Jahre bereits Prognosen sind.

**«Sind die Zahlen aktuell, oder wird aus dem Cache geliefert?»**
- **API-Key nötig:** Nein
- → `fiscal_status()`
- Warum nützlich: Gibt Auskunft über Cache-Frische und Erreichbarkeit je Datensatz — nie ein stilles Leerergebnis, sodass man einer Zahl vertrauen kann, bevor man sie zitiert.

## 🤖 KI-Interessierte & Entwickler:innen

**«Welche gültigen Filterwerte gibt es überhaupt, damit meine Argumente korrekt sind?»**
- **API-Key nötig:** Nein
- → `fiscal_list_dimensions()`
- Warum nützlich: Verwandelt Freitext-Vermutungen in exakte Filterwerte (Variablen, Haushalte, Modelle, Themen, Departemente) — der ideale erste Aufruf eines Agenten.

**«Wie hängen Geldpolitik und Bundesdefizit zusammen?»**
- **API-Key nötig:** Nein
- → `fiscal_headline(variable="saldo", household="bund", year_from=2021)`
- → kombiniert mit [`swiss-snb-mcp`](https://github.com/malkreide) (Geldpolitik / Leitzins)
- Warum nützlich: Portfolio-Kombination — der Zinszyklus (SNB) und das Bundesdefizit (EFV) ergeben zusammen eine Aussage, die keiner der beiden Server allein liefern kann.

## 🔧 Technische Referenz: Tool-Auswahl nach Anwendungsfall

| Ich möchte… | Tool(s) | Auth nötig? |
|---|---|---|
| Kennzahlen-Zeitreihen (Einnahmen/Ausgaben/Saldo/Schuldenquoten) 1990–2029 abrufen | `fiscal_headline` | Nein |
| Den Bundeshaushalt hierarchisch nach Thema aufschlüsseln | `fiscal_budget_breakdown` | Nein |
| Ausgaben nach Departement / Verwaltungseinheit seit 2007 abrufen | `fiscal_by_institution` | Nein |
| Gültige Parameterwerte entdecken (zuerst aufrufen) | `fiscal_list_dimensions` | Nein |
| Cache-Frische und Upstream-Zustand je Datensatz prüfen | `fiscal_status` | Nein |
| (Veraltet) Alias von `fiscal_status` — Rückwärtskompatibilität, wird künftig entfernt | `dump_status` | Nein |
