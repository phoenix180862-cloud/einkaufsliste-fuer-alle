#!/usr/bin/env python3
"""Einkaufsliste – automatische Prüfung (headless Chromium über Playwright).

Aufruf (im Hauptordner der App):  python3 tools/pruefen.py
Startet selbst einen kleinen Server auf 127.0.0.1 und prüft:
  1. Texte: jede Sprache hat genau die Schlüssel und Platzhalter der deutschen Fassung
  2. Katalog: tools/katalog_bauen.py läuft fehlerfrei (gleiche Struktur in allen Sprachen)
  3. Bedienung: hinzufügen (mit Menge), abhaken, löschen + rückgängig, Katalog an/ab, „Erledigte entfernen“ + rückgängig,
     Bearbeiten, Daten nach Neuladen, Teilen-Link → zweiter Browser übernimmt (Duplikate zusammengefasst), Text-Import,
     Sprachwechsel (Katalogartikel übersetzt, Freitext bleibt)
  4. Alle 6 Sprachen bei 390 px Breite: kein waagerechter Überlauf, keine abgeschnittenen Reiter/Knöpfe
  5. Keine Konsolenfehler, keine Anfragen an fremde Server
Ergebnis: Zusammenfassung, Rückgabewert 0 = alles in Ordnung.
"""
import functools, http.server, json, os, re, socketserver, subprocess, sys, threading

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEHLER, OK = [], []


def pruefe(bedingung, text):
    (OK if bedingung else FEHLER).append(text)
    print(('  ok   ' if bedingung else '  FEHLER ') + text, flush=True)


def server():
    class Leise(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    h = functools.partial(Leise, directory=ROOT)
    s = socketserver.ThreadingTCPServer(('127.0.0.1', 0), h); s.daemon_threads = True
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, f'http://127.0.0.1:{s.server_address[1]}/'


def texte_pruefen():
    print('1. Texte')
    js = "global.window={};require(%s);process.stdout.write(JSON.stringify({t:window.EKL_TEXTE,s:window.EKL_SPRACHEN}))" % json.dumps(os.path.join(ROOT, 'texte.js'))
    d = json.loads(subprocess.run(['node', '-e', js], capture_output=True, text=True, check=True).stdout)
    de = d['t']['de']; codes = [s['code'] for s in d['s']]
    pruefe(codes == ['de', 'en', 'cs', 'sk', 'uk', 'pl'], f'Sprachen: {", ".join(codes)} (kein Russisch)')
    for c in codes:
        tx = d['t'].get(c, {})
        fehlt = sorted(set(de) - set(tx)); zuviel = sorted(set(tx) - set(de))
        leer = [k for k, v in tx.items() if not str(v).strip()]
        platz = [k for k in de if k in tx and set(re.findall(r'\{\w+\}', de[k])) != set(re.findall(r'\{\w+\}', tx[k]))]
        teile = [k for k in de if k in tx and (k.startswith('v_') or k == 'menge_vorschlaege') and len(de[k].split('|')) != len(tx[k].split('|'))]
        pruefe(not (fehlt or zuviel or leer or platz or teile), f'{c}: {len(tx)} Schlüssel' + (f' – fehlt {fehlt} zuviel {zuviel} leer {leer} Platzhalter {platz} Teile {teile}' if (fehlt or zuviel or leer or platz or teile) else ''))
        if c != 'de':
            gleich = [k for k in de if tx.get(k) == de[k] and len(de[k]) > 12 and k not in ('menge_vorschlaege',)]
            if gleich: print(f'       Hinweis {c}: unverändert deutsch: {gleich}')
    return codes


def katalog_pruefen():
    print('2. Katalog')
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'katalog_bauen.py')], capture_output=True, text=True)
    print('  ' + r.stdout.strip().replace('\n', '\n  '))
    pruefe(r.returncode == 0, 'Katalog in allen Sprachen vollständig')


def main():
    codes = texte_pruefen(); katalog_pruefen()
    srv, BASE = server()
    fremd, konsole = [], []
    with sync_playwright() as p:
        b = p.chromium.launch()

        def kontext(locale='de-DE', breite=390, hoehe=844):
            c = b.new_context(viewport={'width': breite, 'height': hoehe}, locale=locale, permissions=['clipboard-read', 'clipboard-write'])
            c.on('request', lambda r: (not r.url.startswith(BASE) and not r.url.startswith('data:') and not r.url.startswith('blob:')) and fremd.append(r.url))
            return c

        def seite(c):
            pg = c.new_page()
            pg.on('console', lambda m: m.type == 'error' and konsole.append(m.text))
            pg.on('pageerror', lambda e: konsole.append(str(e)))
            return pg

        print('3. Bedienung')
        c1 = kontext(); pg = seite(c1); pg.goto(BASE); pg.wait_for_timeout(600)
        pruefe(pg.evaluate('EKL.sprache') == 'de', 'Startsprache aus navigator.language (de-DE → de)')
        liste = lambda: pg.evaluate('EKL.liste()')
        for s in ['Äpfel', '2 Bananen', '500 g Hackfleisch gemischt', 'Vollmilch', 'Geschenk für Oma', 'äpfel']:
            pg.fill('#eingabe', s); pg.press('#eingabe', 'Enter')
        L = liste()
        pruefe(len(L) == 5, f'5 Einträge (Duplikat „äpfel“ zusammengefasst) – {len(L)}')
        ban = next((e for e in L if e['name'] == 'Bananen'), {})
        pruefe(ban.get('m') == '2' and ban.get('a') == 'bananen', 'Menge „2“ abgetrennt, Bananen als Katalogartikel (ID bananen)')
        hack = next((e for e in L if e.get('a') == 'hackfleisch-gemischt'), {})
        pruefe(hack.get('m') == '500 g', 'Menge „500 g“ erkannt')
        oma = next((e for e in L if e['name'] == 'Geschenk für Oma'), {})
        pruefe(not oma.get('a') and oma.get('x') == 'Geschenk für Oma', 'Freitext bleibt Freitext')
        # Vorschläge
        pg.fill('#eingabe', 'Tom'); pg.wait_for_timeout(150)
        pruefe(pg.locator('#vorschlaege .vorschlag').count() >= 3, 'Vorschläge erscheinen beim Tippen')
        pg.click('#vorschlaege .vorschlag >> nth=0'); pg.wait_for_timeout(100)
        pruefe(any(e.get('a') == 'tomaten' for e in liste()), 'Vorschlag antippen fügt hinzu')
        # Abhaken
        pg.click('li.eintrag:has-text("Vollmilch") [data-umschalten]')
        pruefe(next(e for e in liste() if e.get('a') == 'vollmilch').get('d') is True, 'Abhaken → im Wagen')
        pruefe(pg.locator('#listeErledigt li').count() == 1, 'Erledigt-Bereich zeigt 1 Eintrag')
        pg.click('#listeErledigt li:has-text("Vollmilch") [data-umschalten]')
        pruefe(not next(e for e in liste() if e.get('a') == 'vollmilch').get('d'), 'Nochmal antippen → wieder offen')
        # Löschen + Rückgängig
        n = len(liste()); pg.click('li.eintrag:has-text("Äpfel") [data-loeschen]')
        pruefe(len(liste()) == n - 1 and pg.is_visible('#toast'), 'Löschen zeigt Hinweis mit Rückgängig')
        pg.click('#toastAktion'); pruefe(len(liste()) == n, 'Rückgängig stellt wieder her')
        # Bearbeiten
        pg.click('li.eintrag:has-text("Äpfel") [data-bearbeiten]'); pg.click('#mengenChips [data-menge="1 kg"]'); pg.click('#formBearb button[type=submit]')
        pruefe(next(e for e in liste() if e.get('a') == 'aepfel').get('m') == '1 kg', 'Menge über Stift + Schnellwahl geändert')
        # Katalog
        pg.click('#tabs [data-tab=lm]'); pg.click('details.kat >> nth=0 >> summary')
        pg.click('.chip[data-aid="birnen"]')
        pruefe(any(e.get('a') == 'birnen' for e in liste()), 'Katalog: antippen setzt auf die Liste')
        pruefe(pg.locator('.chip[data-aid="birnen"].drauf').count() == 1, 'Katalog: Chip markiert')
        pg.click('.chip[data-aid="birnen"]')
        pruefe(not any(e.get('a') == 'birnen' and not e.get('d') for e in liste()), 'Katalog: nochmal antippen nimmt runter')
        pg.click('.chip[data-aid="birnen"]')
        pg.fill('#eingabe', 'zahnpa'); pg.wait_for_timeout(150)
        pruefe(pg.locator('.treffer .chip[data-aid="zahnpasta"]').count() == 1, 'Katalogsuche findet auch andere Bereiche (Zahnpasta)')
        pg.click('[data-suche-weg]'); pg.click('#tabs [data-tab=liste]')
        # Erledigte entfernen
        pg.click('li.eintrag:has-text("Tomaten") [data-umschalten]'); pg.click('li.eintrag:has-text("Bananen") [data-umschalten]')
        n = len(liste()); pg.click('#btnAufraeumen')
        pruefe(len(liste()) == n - 2, 'Erledigte entfernen räumt 2 Einträge ab')
        pg.click('#toastAktion'); pruefe(len(liste()) == n, 'Rückgängig nach dem Aufräumen')
        pg.click('#btnAufraeumen')
        # Neu laden
        vorher = [(e.get('a'), e.get('x'), e.get('m')) for e in liste()]
        pg.reload(); pg.wait_for_timeout(500)
        pruefe([(e.get('a'), e.get('x'), e.get('m')) for e in liste()] == vorher, f'Nach Neuladen alle {len(vorher)} Einträge da')
        # Teilen
        pg.click('#btnTeilen'); pg.click('#btnLinkTeilen'); pg.wait_for_timeout(400)
        link = pg.input_value('#teilenFeld')
        pruefe('#liste=' in link and link.startswith(BASE), f'Teilen-Link erzeugt ({len(link)} Zeichen)')
        try: zw = pg.evaluate('navigator.clipboard.readText()')
        except Exception: zw = ''
        pruefe(zw == link, 'Link in der Zwischenablage (Ersatz für Web-Share)')
        pg.click('#btnTextTeilen'); pg.wait_for_timeout(300); text = pg.input_value('#teilenFeld')
        pruefe(text.startswith('Einkaufsliste') and '- Äpfel (1 kg)' in text and 'Obst' in text, 'Als Text: Liste nach Abteilungen')
        pg.click('#dlgTeilen .kreuz-knopf')
        # zweiter Browser (eigene Liste mit Überschneidung), Sprache Slowakisch
        c2 = kontext('sk-SK'); p2 = seite(c2); p2.goto(BASE); p2.wait_for_timeout(500)
        pruefe(p2.evaluate('EKL.sprache') == 'sk', 'Zweiter Browser startet automatisch auf Slowakisch (sk-SK)')
        p2.fill('#eingabe', 'Jablká'); p2.press('#eingabe', 'Enter'); p2.fill('#eingabe', 'Chlieb'); p2.press('#eingabe', 'Enter')
        p2.goto(link); p2.wait_for_timeout(700)
        pruefe(p2.is_visible('#dlgImport'), 'Link öffnet Frage „Diese Einträge hinzufügen?“')
        namen = p2.locator('#importListe li').all_inner_texts()
        pruefe(any('Banány' in x or 'Jablká' in x for x in namen), 'Empfänger sieht die Artikel auf Slowakisch')
        p2.click('#btnImportJa'); p2.wait_for_timeout(300)
        L2 = p2.evaluate('EKL.liste()')
        pruefe(sum(1 for e in L2 if e.get('a') == 'aepfel') == 1, 'Zusammengeführt: Äpfel/Jablká nur einmal')
        pruefe(next(e for e in L2 if e.get('a') == 'aepfel').get('m') == '1 kg', 'Menge aus dem Link übernommen')
        pruefe(any(e.get('x') == 'Geschenk für Oma' for e in L2), 'Freitext kommt unverändert an')
        pruefe('#' not in p2.url, 'Link-Anhang (#liste=…) danach entfernt')
        # Text einfügen (Weg für installierte iPhone-App)
        p2.click('#btnTeilen'); p2.fill('#empfangenFeld', 'Einkaufsliste\n\nObst\n- Kiwis (6)\n- Erdbeeren\n\nSonstiges\n- Batterien für Uhr'); p2.click('#btnEmpfangen'); p2.wait_for_timeout(300)
        p2.click('#btnImportJa'); L2 = p2.evaluate('EKL.liste()')
        pruefe(any(e.get('a') == 'kiwis' and e.get('m') == '6' for e in L2) and any(e.get('x') == 'Batterien für Uhr' for e in L2), 'Eingefügter Text wird übernommen (deutsche Namen erkannt)')
        # Sprachwechsel
        pg.click('#btnSprache'); pg.click('#spracheListe1 [data-sprache=uk]'); pg.wait_for_timeout(500)
        L = liste()
        pruefe(next(e for e in L if e.get('a') == 'aepfel')['name'] == 'Яблука', 'Sprachwechsel: Katalogartikel auf Ukrainisch (Яблука)')
        pruefe(any(e['name'] == 'Geschenk für Oma' for e in L), 'Sprachwechsel: Freitext bleibt wie getippt')
        pruefe(pg.evaluate('document.documentElement.lang') == 'uk' and pg.inner_text('h1') == 'Список покупок', 'Oberfläche auf Ukrainisch')
        pg.reload(); pg.wait_for_timeout(500)
        pruefe(pg.evaluate('EKL.sprache') == 'uk', 'Sprachwahl wird gemerkt')
        c2.close(); c1.close()

        print('4. Sprachen bei 390 px')
        for code in codes:
            c = kontext(); pg = seite(c); pg.goto(BASE); pg.wait_for_timeout(300)
            pg.evaluate(f'EKL.spracheSetzen("{code}")'); pg.wait_for_timeout(400)
            for aid, m in [('vollmilch', '2'), ('bananen', '6'), ('hackfleisch-gemischt', '500 g'), ('toilettenpapier', ''), ('allzweckreiniger', ''), ('sneakersocken', ''), ('rotkohl', ''), ('erdnussbutter-crunchy', ''), ('waschmaschinenreiniger', '')]:
                pg.evaluate(f'EKL.hinzufuegen(EKL.artikel("{aid}").name, "{m}", true)')
            probleme = pg.evaluate('''() => {
              const w = document.documentElement.clientWidth, p = [];
              if (document.documentElement.scrollWidth > w + 1) p.push('Seite breiter als Bildschirm: ' + document.documentElement.scrollWidth);
              const sichtbar = el => el.offsetParent !== null && getComputedStyle(el).visibility !== 'hidden';
              document.querySelectorAll('body *').forEach(el => {
                if (!sichtbar(el) || el.closest('.fenster[hidden]')) return;
                const r = el.getBoundingClientRect();
                if (r.width && r.right > w + 1 && !el.closest('.vorschlaege')) p.push('ragt rechts hinaus: ' + (el.id || el.className || el.tagName) + ' ' + Math.round(r.right));
              });
              document.querySelectorAll('.tabs button > span, .knopf, .chip, .sprach-wahl, .segment button, .fenster-kopf h2, .abschnitt-titel, .titel h1').forEach(el => {
                if (!sichtbar(el)) return;
                if (el.scrollWidth > el.clientWidth + 1) p.push('abgeschnitten: ' + el.textContent.trim().slice(0, 40));
              });
              return [...new Set(p)];
            }''')
            ansichten = []
            for tab in ['lm', 'hh', 'kl']:
                pg.click(f'#tabs [data-tab={tab}]'); pg.click('details.kat >> nth=0 >> summary')
                ansichten += pg.evaluate('() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1 ? ["Katalog zu breit"] : []')
            pg.click('#tabs [data-tab=liste]')
            for knopf, dlg in [('#btnTeilen', 'dlgTeilen'), ('#btnEinst', 'dlgEinst'), ('#btnHilfe', 'dlgHilfe'), ('#btnSprache', 'dlgSprache')]:
                pg.click(knopf); pg.wait_for_timeout(150)
                ansichten += pg.evaluate(f'''() => {{ const f = document.getElementById("{dlg}").querySelector(".fenster-box"), p = [];
                  if (f.scrollWidth > f.clientWidth + 1) p.push("{dlg} zu breit");
                  f.querySelectorAll(".knopf, .sprach-wahl, .segment button, h2, h3").forEach(el => {{ if (el.offsetParent && el.scrollWidth > el.clientWidth + 1) p.push("{dlg}: abgeschnitten " + el.textContent.trim().slice(0, 30)); }});
                  return p; }}''')
                pg.keyboard.press('Escape')
            alle = probleme + ansichten
            pruefe(not alle, f'{code}: kein Überlauf auf 390 px' + (' – ' + '; '.join(alle[:6]) if alle else ''))
            c.close()
        b.close()
    srv.shutdown()
    print('5. Konsole und Netzwerk')
    pruefe(not konsole, 'keine Konsolenfehler' + (': ' + ' | '.join(konsole[:5]) if konsole else ''))
    pruefe(not fremd, 'nur Anfragen an 127.0.0.1' + (': ' + ', '.join(sorted(set(fremd))[:5]) if fremd else ''))
    print(f'\nErgebnis: {len(OK)} bestanden, {len(FEHLER)} Fehler')
    sys.exit(1 if FEHLER else 0)


if __name__ == '__main__':
    main()
