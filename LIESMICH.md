# Einkaufsliste – „Nie wieder Zettel schreiben“

Kostenlose Einkaufsliste für jeden Haushalt. Läuft im Browser und lässt sich als App auf den Startbildschirm legen.
Ein kostenloses Programm von Thomas Willwacher Fliesenlegermeister e.K. · www.thomas-willwacher.de

- **Kein Server, keine Anmeldung, kein Konto.** Die Liste liegt nur auf dem Gerät (Browser-Speicher `localStorage`).
- **Sechs Sprachen:** Deutsch, English, Čeština, Slovenčina, Українська, Polski – Oberfläche, Katalog, Hilfe und Hilfe-Videos.
- **Katalog:** 1.247 Artikel in 37 Abteilungen und 137 Gruppen (Lebensmittel, Haushalt, Kleidung), sortiert nach dem Weg durch einen typischen Supermarkt.
- Die App läuft im **Hauptordner des Repos** (GitHub Pages, alle Pfade relativ).

## Funktionen

- Artikel oben eintippen (mit Vorschlägen aus dem Katalog) oder im Katalog antippen (nochmal antippen = wieder runter)
- Menge gleich mit eintippen: „2 Milch“, „500 g Hackfleisch“ – oder später über den Stift (mit Schnellwahl)
- Liste nach Abteilungen gruppiert; eigene Einträge werden, wenn möglich, der passenden Abteilung zugeordnet, sonst „Sonstiges“
- Abhaken („Im Wagen“), Löschen mit „Rückgängig“, „Erledigte entfernen“ (ebenfalls rückgängig)
- **Liste teilen** als Link (Web-Share → WhatsApp/SMS/E-Mail, sonst Zwischenablage). Die offenen Einträge stehen komprimiert im Link-Anhang `#liste=…`.
  Wer den Link öffnet, wird gefragt „Diese Einträge zu deiner Liste hinzufügen?“; doppelte werden zusammengefasst, der Anhang danach entfernt.
- **Als Text teilen:** lesbare Liste nach Abteilungen. Link **oder** Text lassen sich im Teilen-Fenster auch einfügen („Liste bekommen?“) – wichtig für iPhones, weil eine installierte iPhone-App einen eigenen Speicher hat.
- Hell / Dunkel / wie das Gerät, Sprachwahl (Kopf und Einstellungen), „Als App installieren“ (Android/Chrome: Systemdialog; iPhone/iPad: Anleitung)
- Hilfe-Fenster mit 5 Themen, je ein Video mit Untertiteln und Sprecherstimme in der gewählten Sprache, Lautstärkeregler
- Freundlicher Leerzustand mit 6 Start-Vorschlägen zum Antippen
- **Firmenlogo im grünen Kopf:** Original (schwarz/rot) auf kleinem weißem Schild – Handy unter dem Titel (32 px hoch, Untertitel entfällt dort), ab 720 px rechts oben (40 px). Antippen öffnet „Über diese App“. Keine Werbetexte auf der Startseite.
- **Einstellungen → „Über diese App“:** Logo, ein Satz („Ein kostenloses Programm von …“), Webseite, E-Mail (keine Telefonnummer) und Links zu den weiteren kostenlosen Programmen
  (Kochbuch „Was isst die Welt?“, TW-CAD, TW Bildstudio)

## Aufbau

| Datei / Ordner | Inhalt |
|---|---|
| `index.html` | Seite mit allen Fenstern |
| `app.css` | Gestaltung: Kopf Grün #1f7a4d, Akzent Gelb #ffd23f, Hintergrund #f3f5f2, Rot nur für Löschen/Warnungen; Archivo / Archivo Narrow, Kyrillisch über Fira Sans |
| `app.js` | Programmlogik |
| `texte.js` | **alle Oberflächentexte** in 6 Sprachen, inkl. Hilfe-Texte und Video-Untertitel (`v_…`) |
| `katalog/quelle/de.txt` | **deutscher Artikelkatalog (Hauptfassung)** mit Abteilungsfarben |
| `katalog/quelle/<sprache>.txt` | Übersetzungen, Zeile für Zeile in derselben Reihenfolge |
| `katalog/*.js` | daraus erzeugt – nicht von Hand ändern |
| `sw.js`, `manifest.webmanifest` | Offline-Betrieb, Installation, automatische Updates |
| `icons/` | App-Symbole Grün/Gelb (erzeugt mit `tools/symbole.py`) |
| `img/logo-auf-hell.webp`, `img/logo-auf-dunkel.webp` | Firmenlogo in **Originalfarben** (schwarz/rot für hellen Grund, weiß/rot für den Dunkelmodus). Nie umfärben, beschneiden oder verzerren; Seitenverhältnis 480:141; Kopf-Schild 32 px (Handy) / 40 px (ab 720 px) hoch, „Über diese App“ 200 px breit |
| `fonts/` | Schriften (lokal, OFL-Lizenz – siehe `OFL-*.txt`) |
| `hilfe/videos/<sprache>/<thema>.mp4/.jpg`, `info.json` | Hilfe-Videos |
| `tools/` | Werkzeuge zum Bauen, Prüfen, Aufnehmen (werden von der App nicht geladen) |

### Gespeicherte Daten (nur im Browser, Präfix `ekl_`)
`ekl_liste` (Liste), `ekl_sprache`, `ekl_thema`, `ekl_lautstaerke`, `ekl_install_weg` (Installations-Hinweis ausgeblendet).
Katalogartikel werden mit fester **Artikel-ID** gespeichert und deshalb nach einem Sprachwechsel in der neuen Sprache angezeigt;
eigene Einträge bleiben so, wie sie getippt wurden. Geteilte Links übertragen ebenfalls IDs bzw. Freitext.

## Pflege

**Version erhöhen bei jeder Änderung:** `VERSION` in `app.js` **und** in `sw.js` (gleiche Nummer). Dadurch holt sich jedes Gerät beim nächsten Öffnen den neuen Stand automatisch (Service Worker mit `skipWaiting` / `clients.claim`, „Netz zuerst“).

**Katalog ändern** (neuer Artikel, neue Gruppe):
1. In `katalog/quelle/de.txt` eintragen (Artikel mit Semikolon trennen).
2. In **allen** Sprachdateien an derselben Stelle übersetzen.
3. `python3 tools/katalog_bauen.py` – meldet genau, wo eine Zeile oder ein Artikel fehlt.

Die Artikel-ID entsteht aus dem deutschen Namen (z. B. „Äpfel rot“ → `aepfel-rot`). Vorhandene deutsche Namen darum **nicht umbenennen**,
sonst erkennen ältere Listen und Links den Artikel nicht mehr (er wird dann mit dem gespeicherten Namen angezeigt bzw. beim Übernehmen übersprungen).
Neue Artikel hinzufügen ist jederzeit unproblematisch.

**Texte ändern:** in `texte.js`. Jede Sprache braucht dieselben Schlüssel und Platzhalter wie Deutsch (prüft `tools/pruefen.py`).
Firmenname und Web-Adresse in der Fußzeile bleiben in allen Sprachen deutsch.

**App-Symbole neu zeichnen:** `python3 tools/symbole.py`

## Prüfen

```
pip install playwright && python3 -m playwright install chromium
python3 tools/pruefen.py
```
Prüft Texte (Schlüssel/Platzhalter aller Sprachen), Katalog-Vollständigkeit, die Bedienung (hinzufügen, Menge, abhaken, löschen + rückgängig,
Katalog, aufräumen, Neuladen, Teilen-Link in einem zweiten Browser übernehmen, Text einfügen, Sprachwechsel), alle 6 Sprachen auf 390 px Breite
auf Überlauf, Konsolenfehler und dass keine fremden Server angefragt werden.

## Hilfe-Videos neu aufnehmen

Nötig, sobald sich etwas Sichtbares ändert oder die Untertitel (`v_…` in `texte.js`) geändert werden.

```
pip install piper-tts playwright
python3 tools/hilfe_videos.py                    # alle Sprachen, alle Themen
python3 tools/hilfe_videos.py sk uk              # nur diese Sprachen
python3 tools/hilfe_videos.py de --themen teilen # nur ein Thema
```
- Format 390×844 (Handy), gelber Kreis zeigt den „Finger“, Untertitel im Bild, Ton per Piper-Sprecherstimme (offline).
- Stimmen (nicht im Repo) unter `$EKL_TTS` (Standard `/home/claude/tts`), je Sprache ein Ordner aus den sherpa-onnx-Paketen
  (`https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-<stimme>.tar.bz2`):
  `de_DE-thorsten-high`, `en_GB-alan-medium`, `cs_CZ-jirka-medium`, `sk_SK-lili-medium`, `uk_UA-ukrainian_tts-medium` (Sprecher 1), `pl_PL-gosia-medium`.
- Fehlt eine Stimme, wird die Sprache ohne Ton aufgenommen; `hilfe/videos/info.json` vermerkt das und die App zeigt „Video mit Untertiteln“.
- Sprachausgaben werden in `$EKL_TTS/cache` zwischengespeichert.

## Bildschirmfotos für die Webseite

`python3 tools/bildschirmfotos.py [Zielordner]` – Standard `/home/claude/frei-pakete/screens/einkaufsliste/`
(PNG 390×844 bei 2-facher Pixeldichte, Tablet 1180×820): Liste, Katalog, Eingabe mit Vorschlägen, Teilen, Hilfe, Dunkelmodus, Tablet quer, Slowakisch, Ukrainisch.

## Datenschutz

Keine Anfragen an fremde Server: Schriften, Symbole, Katalog und Videos liegen im Repo. Kein Tracking, keine Cookies.
Beim Teilen steht die Liste im Link, den die Person selbst verschickt. Impressum und Datenschutz: Links in der Fußzeile auf www.thomas-willwacher.de.
