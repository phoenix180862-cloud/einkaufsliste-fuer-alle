#!/usr/bin/env python3
"""Einkaufsliste – Artikelkatalog bauen und prüfen.

Aufruf (im Hauptordner der App):  python3 tools/katalog_bauen.py

Quelle:   katalog/quelle/de.txt          deutsche Hauptfassung (mit Farben)
          katalog/quelle/<sprache>.txt   Übersetzungen, Zeile für Zeile in derselben Reihenfolge
Ergebnis: katalog/aufbau.js              Bereiche, Abteilungen (Farbe), Gruppen, Artikel-IDs
          katalog/<sprache>.js           Namen in der jeweiligen Sprache (auch de.js)

Format:
  @lm                                   Bereich: lm = Lebensmittel, hh = Haushalt, kl = Kleidung
  K Obst | #C8553D                      Abteilung (Farbe nur in de.txt)
  G Äpfel & Birnen = Äpfel; Äpfel rot   Gruppe = Artikel, getrennt mit Semikolon
  # …                                   Kommentar

Geprüft wird: gleiche Zahl an Abteilungen, Gruppen und Artikeln in jeder Sprache wie im Deutschen,
eindeutige Artikel-IDs, keine leeren Namen, keine doppelten Namen innerhalb einer Sprache (Warnung).
"""
import json, os, re, sys

HIER = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HIER)
QUELLE = os.path.join(ROOT, 'katalog', 'quelle'); ZIEL = os.path.join(ROOT, 'katalog')
SPRACHEN = ['de', 'en', 'cs', 'sk', 'uk', 'pl']


def artikel_id(s):
    """Artikel-ID aus dem deutschen Namen – muss zu nichts anderem passen, wird nur hier gebildet."""
    s = s.lower()
    for a, b in [('ä', 'ae'), ('ö', 'oe'), ('ü', 'ue'), ('ß', 'ss'), ('é', 'e'), ('è', 'e'), ('ê', 'e'), ('ç', 'c'), ('à', 'a'), ('â', 'a'), ('ñ', 'n'), ('î', 'i'), ('ô', 'o'), ('&', ' und ')]:
        s = s.replace(a, b)
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')


def lesen(pfad):
    erg = {}; typ = None; fehler = []
    for nr, zeile in enumerate(open(pfad, encoding='utf-8'), 1):
        zeile = zeile.strip()
        if not zeile or zeile.startswith('#'): continue
        if zeile.startswith('@'): typ = zeile[1:].split('#')[0].strip(); erg[typ] = []; continue
        if typ is None: fehler.append(f'Zeile {nr}: Bereich (@lm/@hh/@kl) fehlt davor'); continue
        if zeile.startswith('K '):
            name, _, farbe = zeile[2:].partition('|')
            erg[typ].append({'name': name.strip(), 'farbe': farbe.strip(), 'gruppen': []}); continue
        if zeile.startswith('G '):
            if ' = ' not in zeile: fehler.append(f'Zeile {nr}: „ = “ fehlt'); continue
            if not erg[typ]: fehler.append(f'Zeile {nr}: Gruppe ohne Abteilung'); continue
            name, rest = zeile[2:].split(' = ', 1)
            erg[typ][-1]['gruppen'].append({'name': name.strip(), 'artikel': [a.strip() for a in rest.split(';') if a.strip()]})
            continue
        fehler.append(f'Zeile {nr}: unbekannt: {zeile[:50]}')
    return erg, fehler


def vergleichen(de, tr, sp):
    f = []
    for typ in de:
        if typ not in tr: f.append(f'{sp}: Bereich @{typ} fehlt'); continue
        if len(de[typ]) != len(tr[typ]): f.append(f'{sp} @{typ}: {len(tr[typ])} statt {len(de[typ])} Abteilungen'); continue
        for h, t in zip(de[typ], tr[typ]):
            if len(h['gruppen']) != len(t['gruppen']): f.append(f'{sp} {h["name"]}: {len(t["gruppen"])} statt {len(h["gruppen"])} Gruppen'); continue
            for g, tg in zip(h['gruppen'], t['gruppen']):
                if len(g['artikel']) != len(tg['artikel']):
                    f.append(f'{sp} {h["name"]} › {g["name"]}: {len(tg["artikel"])} statt {len(g["artikel"])} Artikel')
    return f


def main():
    de, f = lesen(os.path.join(QUELLE, 'de.txt'))
    alle_fehler = ['de: ' + x for x in f]; warnungen = []
    ids = {}; aufbau = {}
    for typ, abt in de.items():
        aufbau[typ] = []
        for h in abt:
            if not re.fullmatch(r'#[0-9A-Fa-f]{6}', h['farbe']): alle_fehler.append(f'de: Farbe fehlt bei {h["name"]}')
            gr = []
            for g in h['gruppen']:
                liste = []
                for a in g['artikel']:
                    i = artikel_id(a)
                    if i in ids: alle_fehler.append(f'ID doppelt: {a} / {ids[i]} → {i}')
                    ids[i] = a; liste.append(i)
                gr.append(liste)
            aufbau[typ].append({'farbe': h['farbe'], 'gruppen': gr})
    anz_k = sum(len(v) for v in de.values()); anz_g = sum(len(h['gruppen']) for v in de.values() for h in v)
    print(f'Deutsch: {len(de)} Bereiche, {anz_k} Abteilungen, {anz_g} Gruppen, {len(ids)} Artikel')
    kopf = '// Automatisch erzeugt von tools/katalog_bauen.py aus katalog/quelle/ – nicht von Hand ändern.\n'
    open(os.path.join(ZIEL, 'aufbau.js'), 'w', encoding='utf-8').write(
        kopf + 'window.EKL_KATALOG_AUFBAU=%s;\n' % json.dumps(aufbau, ensure_ascii=False, separators=(',', ':')))
    for sp in SPRACHEN:
        p = os.path.join(QUELLE, f'{sp}.txt')
        if not os.path.exists(p): alle_fehler.append(f'{sp}: Datei fehlt'); continue
        tr, f = (de, []) if sp == 'de' else lesen(p)
        f = [f'{sp}: {x}' for x in f] + vergleichen(de, tr, sp); alle_fehler += f
        if f: continue
        gesehen = {}
        for abt in tr.values():
            for h in abt:
                for g in h['gruppen']:
                    for a in g['artikel']:
                        k = a.lower()
                        if k in gesehen: warnungen.append(f'{sp}: Name doppelt „{a}“')
                        gesehen[k] = 1
        kompakt = {typ: [[h['name'], [[g['name'], g['artikel']] for g in h['gruppen']]] for h in abt] for typ, abt in tr.items()}
        js = kopf + 'window.EKL_KATALOG_NAMEN=window.EKL_KATALOG_NAMEN||{};window.EKL_KATALOG_NAMEN[%s]=%s;\n' % (
            json.dumps(sp), json.dumps(kompakt, ensure_ascii=False, separators=(',', ':')))
        open(os.path.join(ZIEL, f'{sp}.js'), 'w', encoding='utf-8').write(js)
        print(f'{sp}: ok ({os.path.getsize(os.path.join(ZIEL, f"{sp}.js")) // 1024} KB)')
    if warnungen: print('\nHinweise:'); print('\n'.join(warnungen))
    if alle_fehler:
        print('\nFEHLER:'); print('\n'.join(alle_fehler)); sys.exit(1)
    print('Alles in Ordnung.')


if __name__ == '__main__':
    main()
