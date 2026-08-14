# Herkunft der Fixtures

**Erzeugt von `scripts/record_fixtures.py`. Nicht von Hand pflegen.**

Aufgezeichnet am **2026-08-14** von den beiden Quellen dieses Servers:
`https://www.data.finance.admin.ch/static/assets/datasets` und `https://www.efv.admin.ch/dam/de/sd-web`.

Ohne Datum ist «aufgezeichnet» nach zwei Jahren von «ausgedacht» nicht
mehr zu unterscheiden — die Datei sieht gleich aus.

**Es sind Ausschnitte, keine Vollabzuege.** Die Quelldateien sind 0.5 bis
5 MB gross. Aufgezeichnet ist je Datei die **unveraenderte Kopfzeile**
und eine Auswahl Datenzeilen; keine Spalte wurde entfernt. Eine Fixture
belegt damit die *Form* der Antwort und einen datierten Ausschnitt ihres
Inhalts — nicht den Bestand. Aussagen ueber Vollstaendigkeit gehoeren in
Live-Tests.

**Die Zeilen sind gewaehlt, nicht genommen.** Die ersten Zeilen jeder
Datei zeigen immer nur eine Variante: `budget.csv` beginnt ausschliesslich
mit Hierarchie-Ebene 1, obwohl der Client bis Ebene 8 parst, und
`headline.csv` enthaelt in den ersten tausend Zeilen keine einzige der
`NA`-Zeilen, auf die `_NULLISH` reagiert. Eine Kopfauswahl haette beide
Faelle nie belegt.

Fehlerpfade — 404, Timeouts, maskierte 4xx — bleiben handgeschrieben.
Die lassen sich nicht auf Zuruf aufzeichnen.

## `headline.csv`

- **Quelle:** `https://www.data.finance.admin.ch/static/assets/datasets/fs_dashboard/main_extern.csv`
- **Aufgezeichnet:** 2026-08-14
- **Auswahl:** Kopfzeile unveraendert, 7 von 6579 Zeilen: variable='aktiven', model='fs' mit je einer Zeile je `hh`-Wert — zusammen abfragbar —, dazu die `NA`-Zeile, auf die `_NULLISH` reagiert
- **Groesse:** 453 B (Quelle: 6579 Datenzeilen)
- **SHA-256:** `f577ffb637268edfa1c9f58b6a676ea8ce2cc5b39f471ffbfbb264fb675fbff7`

## `budget.csv`

- **Quelle:** `https://www.efv.admin.ch/dam/de/sd-web/m9aWXSnsRvNO/bundeshaushalt_de.csv`
- **Aufgezeichnet:** 2026-08-14
- **Auswahl:** Kopfzeile unveraendert, 8 von 19892 Zeilen: topic='Erfolgsrechnung (ab 2023)', year=2023 mit je einer Zeile je Hierarchie-Ebene — zusammen abfragbar; die Datei beginnt ausschliesslich mit Ebene 1
- **Groesse:** 2482 B (Quelle: 19892 Datenzeilen)
- **SHA-256:** `646f9ab7d876575dcf0248e66aed1be3bd324721ba6b14692b8d3a43b8630e12`

## `institutions.csv`

- **Quelle:** `https://www.efv.admin.ch/dam/de/sd-web/LheAU2Ioeux7/institutionen_de.csv`
- **Aufgezeichnet:** 2026-08-14
- **Auswahl:** Kopfzeile unveraendert, 10 von 8901 Zeilen: variable_name='Anzahl Vollzeitstellen', year=2007 mit je einer Zeile je Departement und je Hierarchie-Ebene — zusammen abfragbar
- **Groesse:** 1210 B (Quelle: 8901 Datenzeilen)
- **SHA-256:** `70ea79985208af4a0782fdcd52cfa6cf927a0bfc9bc878b3f361d95117a3a50b`
