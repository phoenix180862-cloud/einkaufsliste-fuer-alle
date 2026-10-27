#!/usr/bin/env python3
"""Einkaufsliste – Bildschirmfotos für die Programmseite auf der Webseite.
Aufruf (im Hauptordner der App):  python3 tools/bildschirmfotos.py [Zielordner]
Standard-Ziel: /home/claude/frei-pakete/screens/einkaufsliste/   (PNG, Handy 390×844 bei 2-facher Pixeldichte)"""
import functools, http.server, json, os, socketserver, sys, threading
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZIEL = sys.argv[1] if len(sys.argv) > 1 else '/home/claude/frei-pakete/screens/einkaufsliste'
# realistisch gefüllte Beispielliste: (Katalog-ID oder None, Freitext, Menge, abgehakt)
LISTE = [('aepfel', '', '1 kg', False), ('bananen', '', '', False), ('tomaten', '', '500 g', False), ('vollmilch', '', '2', False),
         ('butter', '', '', False), ('eier', '', '10', False), ('hackfleisch-gemischt', '', '500 g', False), ('toastbrot', '', '', True),
         ('kaffeebohnen', '', '', True), ('spuelmittel', '', '', False), ('toilettenpapier', '', '', True), (None, 'Geburtstagskarte für Oma', '', False)]
EIGEN = {'sk': 'Pohľadnica pre babku', 'uk': 'Листівка для бабусі'}


def saat(sp, thema='hell', leer=False):
    e = []
    for i, (a, x, m, d) in enumerate(LISTE):
        z = {'id': f's{i}', 't': i + 1}
        if a: z['a'] = a; z['x'] = a
        else: z['x'] = EIGEN.get(sp, x)
        if m: z['m'] = m
        if d: z['d'] = True; z['td'] = 100 + i
        e.append(z)
    if leer: e = []
    return ("try{localStorage.setItem('ekl_sprache','%s');localStorage.setItem('ekl_liste',%s);localStorage.setItem('ekl_install_weg','1');localStorage.setItem('ekl_thema','%s');}catch(e){}"
            % (sp, json.dumps(json.dumps({'v': 1, 'e': e})), thema))


def main():
    os.makedirs(ZIEL, exist_ok=True)
    class Leise(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = socketserver.ThreadingTCPServer(('127.0.0.1', 0), functools.partial(Leise, directory=ROOT)); srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    BASE = f'http://127.0.0.1:{srv.server_address[1]}/'
    with sync_playwright() as p:
        b = p.chromium.launch()

        def seite(sp='de', thema='hell', w=390, h=844, leer=False):
            c = b.new_context(viewport={'width': w, 'height': h}, device_scale_factor=2, color_scheme='dark' if thema == 'dunkel' else 'light',
                              permissions=['clipboard-read', 'clipboard-write'])
            c.add_init_script(saat(sp, thema, leer)); pg = c.new_page(); pg.goto(BASE); pg.wait_for_timeout(900)
            pg.evaluate('document.fonts.ready'); return c, pg

        def foto(pg, name): pg.mouse.move(2, 300); pg.wait_for_timeout(300); pg.screenshot(path=os.path.join(ZIEL, name)); print(name)

        c, pg = seite(); foto(pg, '01-liste.png')
        pg.click('#tabs [data-tab=lm]'); pg.click('details.kat >> nth=0 >> summary'); pg.click('details.kat >> nth=1 >> summary')
        pg.evaluate('window.scrollTo(0,0)'); foto(pg, '02-katalog-lebensmittel.png')
        pg.click('#tabs [data-tab=liste]'); pg.click('#eingabe'); pg.keyboard.type('Tom', delay=60); pg.wait_for_timeout(200)
        foto(pg, '03-eingabe-vorschlaege.png')
        pg.keyboard.press('Escape'); pg.fill('#eingabe', ''); pg.click('h1')
        pg.click('#btnTeilen'); pg.wait_for_timeout(300); foto(pg, '04-teilen.png'); pg.keyboard.press('Escape')
        pg.click('#btnHilfe'); pg.wait_for_timeout(300); pg.click('#hilfeThemen details >> nth=0 >> summary'); pg.wait_for_timeout(1200)
        foto(pg, '05-hilfe.png'); c.close()
        c, pg = seite('de', 'dunkel'); foto(pg, '06-liste-dunkel.png'); c.close()
        c, pg = seite('de', 'hell', 1180, 820)
        pg.click('details.kat >> nth=0 >> summary'); pg.evaluate("document.getElementById('ansichtKatalog').scrollTop=0"); foto(pg, '07-tablet-quer.png'); c.close()
        c, pg = seite('sk'); foto(pg, '08-liste-slowakisch.png'); c.close()
        c, pg = seite('uk'); foto(pg, '09-liste-ukrainisch.png'); c.close()
        c, pg = seite(); pg.click('#btnEinst'); pg.wait_for_timeout(300)
        pg.evaluate("document.getElementById('ueberTitel').scrollIntoView({block:'start'})"); foto(pg, '10-ueber-diese-app.png'); c.close()
        c, pg = seite(leer=True); foto(pg, '11-leere-liste.png'); c.close()
        b.close()
    srv.shutdown()


if __name__ == '__main__':
    main()
