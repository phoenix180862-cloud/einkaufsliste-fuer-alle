#!/usr/bin/env python3
"""Einkaufsliste – Hilfe-Videos aufnehmen (Playwright, Handyformat 390×844).

Aufruf (im Hauptordner der App):
    python3 tools/hilfe_videos.py                 alle Sprachen, alle Themen
    python3 tools/hilfe_videos.py de sk           nur diese Sprachen
    python3 tools/hilfe_videos.py de --themen teilen,katalog
Startet selbst einen Server auf 127.0.0.1. Ergebnis je Sprache und Thema:
    hilfe/videos/<sprache>/<thema>.mp4  (H.264 + AAC, läuft auf allen Handys)
    hilfe/videos/<sprache>/<thema>.jpg  (Vorschaubild)
    hilfe/videos/info.json              ({"de": {"ton": true}, …} – die App zeigt bei ton=false einen Untertitel-Hinweis)

Untertitel = die Texte v_<thema> aus texte.js (eine Zeile je Abschnitt, mit | getrennt) – Texte also dort ändern.
Sprecherstimme: Piper-TTS (offline). Stimmen liegen außerhalb der App unter $EKL_TTS (Standard /home/claude/tts):
    de  vits-piper-de_DE-thorsten-high      en  vits-piper-en_GB-alan-medium     cs  vits-piper-cs_CZ-jirka-medium
    sk  vits-piper-sk_SK-lili-medium        uk  vits-piper-uk_UA-ukrainian_tts-medium (Sprecher 1)   pl  vits-piper-pl_PL-gosia-medium
Fehlt eine Stimme (oder das Python-Paket piper-tts), wird diese Sprache ohne Ton aufgenommen – nur mit Untertiteln.
Bei JEDER sichtbaren Änderung der App die betroffenen Videos neu aufnehmen.
"""
import functools, hashlib, http.server, json, os, re, shutil, socketserver, subprocess, sys, tempfile, threading, time, wave

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'hilfe', 'videos')
TTS = os.environ.get('EKL_TTS', '/home/claude/tts')
TONCACHE = os.environ.get('EKL_TONCACHE', os.path.join(TTS, 'cache'))
W, H = 390, 844
SPRACHEN = ['de', 'en', 'cs', 'sk', 'uk', 'pl']
THEMEN = ['hinzufuegen', 'katalog', 'abhaken', 'teilen', 'installieren']
STIMMEN = {'de': ('vits-piper-de_DE-thorsten-high', None), 'en': ('vits-piper-en_GB-alan-medium', None),
           'cs': ('vits-piper-cs_CZ-jirka-medium', None), 'sk': ('vits-piper-sk_SK-lili-medium', None),
           'uk': ('vits-piper-uk_UA-ukrainian_tts-medium', 1), 'pl': ('vits-piper-pl_PL-gosia-medium', None)}
# Beispielliste je Sprache: Katalog-IDs (+ Menge) und ein eigener Eintrag
BEISPIEL = [('aepfel', '1 kg'), ('bananen', ''), ('kartoffeln', '2 kg'), ('butter', ''), ('eier', '10'), ('toastbrot', ''), ('spuelmittel', ''), ('toilettenpapier', '')]
EIGEN = {'de': 'Geburtstagskarte', 'en': 'Birthday card', 'cs': 'Přání k narozeninám', 'sk': 'Pohľadnica k narodeninám', 'uk': 'Листівка на день народження', 'pl': 'Kartka urodzinowa'}

INIT = r"""
(() => {
  const mk = () => {
    if (document.getElementById('__cur')) return;
    const c = document.createElement('div'); c.id = '__cur';
    c.style.cssText = 'position:fixed;z-index:99999;left:-40px;top:-40px;width:30px;height:30px;margin:-15px 0 0 -15px;border-radius:50%;border:3px solid #facc15;background:rgba(250,204,21,.28);pointer-events:none;transition:transform .08s';
    document.body.append(c);
    const cap = document.createElement('div'); cap.id = '__cap';
    cap.style.cssText = 'position:fixed;z-index:99998;left:12px;right:12px;bottom:92px;background:rgba(17,17,17,.94);color:#fff;font:600 18px/1.35 Archivo,system-ui,sans-serif;padding:12px 14px;border-radius:12px;border:2px solid #facc15;pointer-events:none;display:none;text-align:center';
    document.body.append(cap);
    addEventListener('mousemove', e => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; }, true);
    addEventListener('mousedown', () => c.style.transform = 'scale(.7)', true); addEventListener('mouseup', () => c.style.transform = '', true);
    window.__cap = t => { cap.style.display = t ? 'block' : 'none'; cap.textContent = t || ''; };
  };
  if (document.readyState !== 'loading') mk(); else addEventListener('DOMContentLoaded', mk);
})();
"""


# ───── Stimme ─────
_stimmen = {}
def stimme(sp):
    if sp in _stimmen: return _stimmen[sp]
    ordner, sprecher = STIMMEN[sp]; v = None
    try:
        onnx = [f for f in os.listdir(os.path.join(TTS, ordner)) if f.endswith('.onnx')][0]
        from piper import PiperVoice
        v = (PiperVoice.load(os.path.join(TTS, ordner, onnx)), sprecher, os.path.join(ordner, onnx))
    except Exception as e:
        print(f'  ({sp}: keine Stimme – {str(e)[:80]}) → ohne Ton', flush=True)
    _stimmen[sp] = v; return v


AUSSPRACHE = {
    'de': [(r'\bWhatsApp\b', 'Wotsäpp'), (r'\bSMS\b', 'S M S'), (r'\biPhone\b', 'Ei-Fohn'), (r'\bApp\b', 'Äpp')],
    'en': [(r'\bWhatsApp\b', 'Whats App')],
    'cs': [(r'\bWhatsApp\b', 'vocap'), (r'\bSMS\b', 'esemes'), (r'\be-mail\b', 'imejl'), (r'\biPhonu\b', 'ajfounu'), (r'\biPhone\b', 'ajfoun')],
    'sk': [(r'\bWhatsApp\b', 'vocap'), (r'\bSMS\b', 'esemes'), (r'\be-mail\b', 'imejl'), (r'\biPhone\b', 'ajfón')],
    'pl': [(r'\bWhatsApp\b', 'łotsap'), (r'\bSMS\b', 'esemes'), (r'\be-mail\b', 'imejl'), (r'\biPhonie\b', 'ajfonie'), (r'\biPhone\b', 'ajfon')],
    'uk': [(r'WhatsApp', 'вотсап'), (r'SMS', 'есемес'), (r'e-mail', 'імейл'), (r'iPhone', 'айфоні'), (r'Safari', 'сафарі')],
}
def sprechbar(sp, t):
    for a, b in AUSSPRACHE.get(sp, []): t = re.sub(a, b, t)
    t = re.sub(r'[„“”"«»‚‘]', '', t).replace(' – ', ', ').replace('–', ', ').replace('…', '.')
    if sp == 'uk': t = t.lower().replace('’', "'"); t = re.sub(r'[a-z]', '', t)
    return re.sub(r'\s+', ' ', t).strip()


def sprich(sp, text):
    v = stimme(sp)
    if not v: return None, 0
    voice, sprecher, name = v
    os.makedirs(TONCACHE, exist_ok=True)
    f = os.path.join(TONCACHE, hashlib.sha1((name + '|' + str(sprecher) + '|' + text).encode()).hexdigest()[:16] + '.wav')
    if not os.path.exists(f):
        from piper import SynthesisConfig
        cfg = SynthesisConfig(speaker_id=sprecher, length_scale=1.05)
        with wave.open(f, 'wb') as w: voice.synthesize_wav(text, w, syn_config=cfg)
    with wave.open(f) as w: return f, w.getnframes() / w.getframerate()


# ───── Szenen-Helfer ─────
class S:
    def __init__(s, pg, sp, texte):
        s.pg = pg; s.sp = sp; s.t0 = time.time(); s.ton = []; s.c = texte['v_' + s.thema].split('|') if hasattr(s, 'thema') else []
    def cap(s, i, extra=0):
        text = s.c[i] if isinstance(i, int) else i
        f, dauer = sprich(s.sp, sprechbar(s.sp, text))
        s.pg.evaluate('t => window.__cap && window.__cap(t)', text)
        if f: s.ton.append((time.time() - s.t0, f))
        s.pg.wait_for_timeout(int(max(2200, dauer * 1000 + 500)) + extra)
    def mitte(s, sel):
        loc = s.pg.locator(sel).first; loc.scroll_into_view_if_needed(); s.pg.wait_for_timeout(120)
        b = loc.bounding_box(); return b['x'] + b['width'] / 2, b['y'] + b['height'] / 2
    def zeige(s, sel): x, y = s.mitte(sel); s.pg.mouse.move(x, y, steps=16); s.pg.wait_for_timeout(250)
    def klick(s, sel, warte=450):
        x, y = s.mitte(sel); s.pg.mouse.move(x, y, steps=16); s.pg.wait_for_timeout(150)
        s.pg.mouse.down(); s.pg.wait_for_timeout(70); s.pg.mouse.up(); s.pg.wait_for_timeout(warte)
    def tippe(s, text): s.pg.keyboard.type(text, delay=120); s.pg.wait_for_timeout(300)
    def name(s, aid): return s.pg.evaluate(f'EKL.artikel("{aid}").name')


def sc_hinzufuegen(s):
    s.zeige('#eingabe'); s.cap(0)
    s.klick('#eingabe'); s.tippe(s.name('tomaten')[:3]); s.cap(1)
    s.klick('#vorschlaege .vorschlag >> nth=0', 700)
    s.klick('#eingabe'); s.tippe('2 ' + s.name('vollmilch')); s.cap(2, -800)
    s.klick('.plus', 900)
    s.zeige('li.eintrag.neu-markiert, li.eintrag:has-text("%s")' % s.name('vollmilch')); s.cap(3)
    s.klick('li.eintrag:has-text("%s") [data-bearbeiten]' % s.name('vollmilch'), 600); s.cap(4, -600)
    s.klick('#mengenChips .chip >> nth=6', 500); s.klick('#formBearb button[type=submit]', 900)


def sc_katalog(s):
    s.zeige('#tabs [data-tab=lm]'); s.cap(0, -900); s.klick('#tabs [data-tab=lm]', 600)
    s.klick('details.kat >> nth=0 >> summary', 500); s.cap(1, -1200)
    s.klick('.chip[data-aid="kiwis"]', 500); s.klick('.chip[data-aid="erdbeeren"]', 700)
    s.cap(2, -900); s.klick('.chip[data-aid="kiwis"]', 900)
    s.klick('#tabs [data-tab=liste]', 500); s.zeige('#offenBereich .abschnitt >> nth=1'); s.cap(3)


def sc_abhaken(s):
    a = s.name('aepfel'); b = s.name('butter')
    s.zeige('li.eintrag:has-text("%s")' % a); s.cap(0, -1000)
    s.klick('li.eintrag:has-text("%s") [data-umschalten]' % a, 500); s.klick('li.eintrag:has-text("%s") [data-umschalten]' % b, 700)
    s.cap(1, -900); s.klick('#listeErledigt li:has-text("%s") [data-umschalten]' % b, 900)
    s.cap(2, -1200); s.klick('li.eintrag:has-text("%s") [data-loeschen]' % s.name('toastbrot'), 1000); s.klick('#toastAktion', 900)
    s.zeige('#btnAufraeumen'); s.cap(3, -900); s.klick('#btnAufraeumen', 1200)


def sc_teilen(s):
    s.zeige('#btnTeilen'); s.cap(0, -900); s.klick('#btnTeilen', 600)
    s.zeige('#btnLinkTeilen'); s.cap(1, -900); s.klick('#btnLinkTeilen', 900)
    link = s.pg.input_value('#teilenFeld')
    s.zeige('#btnTextTeilen'); s.cap(4, -900); s.klick('#btnTextTeilen', 1200)
    s.klick('#dlgTeilen .kreuz-knopf', 400)
    # Empfänger: eigene kleine Liste, andere Sprache (zeigt: Artikel kommen in SEINER Sprache an)
    andere = 'sk' if s.sp == 'de' else 'de'
    s.pg.evaluate("([sp, l]) => { localStorage.setItem('ekl_sprache', sp); localStorage.setItem('ekl_liste', JSON.stringify({v:1,e:[{id:'e1',a:'kaffee',x:'Kaffee',t:1}]})); }", [andere, None])
    s.pg.goto('about:blank'); s.pg.goto(link); s.pg.wait_for_timeout(900); s.cap(2, -400)   # echtes Neuladen, nicht nur Anhang-Wechsel
    s.zeige('#importListe li >> nth=0'); s.cap(3, -600)
    s.klick('#btnImportJa', 1500)


def sc_installieren(s):
    s.pg.evaluate('EKL.installTest()')
    s.zeige('#btnEinst'); s.cap(0, -900); s.klick('#btnEinst', 700)
    s.pg.evaluate("document.querySelector('#einstInstall').scrollIntoView({block:'center'})"); s.pg.wait_for_timeout(300)
    s.zeige('[data-installieren]'); s.cap(1)
    s.pg.evaluate('window.__cap("")'); s.klick('#dlgEinst .kreuz-knopf', 400); s.pg.evaluate('EKL.iosAnleitung()'); s.pg.wait_for_timeout(500); s.cap(2, 400)
    s.klick('#dlgIos .breit-knopf', 500); s.cap(3)


SZENEN = {'hinzufuegen': sc_hinzufuegen, 'katalog': sc_katalog, 'abhaken': sc_abhaken, 'teilen': sc_teilen, 'installieren': sc_installieren}


def server():
    class Leise(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    s = socketserver.ThreadingTCPServer(('127.0.0.1', 0), functools.partial(Leise, directory=ROOT)); s.daemon_threads = True
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, f'http://127.0.0.1:{s.server_address[1]}/'


def ton_einmischen(video, ton, trim, ziel):
    ins, flt = [], []
    for i, (t, f) in enumerate(ton):
        ins += ['-i', f]; ms = max(0, int((t - trim) * 1000)); flt.append(f'[{i + 1}:a]aresample=48000,adelay={ms}:all=1[a{i}]')
    flt.append(''.join(f'[a{i}]' for i in range(len(ton))) + f'amix=inputs={len(ton)}:normalize=0:dropout_transition=0,volume=0.95,alimiter=limit=0.89,apad[a]')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', str(trim), '-i', video] + ins + ['-filter_complex', ';'.join(flt), '-map', '0:v', '-map', '[a]',
                    '-c:v', 'libx264', '-preset', 'slow', '-crf', '27', '-pix_fmt', 'yuv420p', '-r', '25', '-c:a', 'aac', '-b:a', '64k', '-ac', '1', '-shortest', '-movflags', '+faststart', ziel], check=True)


def ohne_ton(video, trim, ziel):
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', str(trim), '-i', video, '-an', '-c:v', 'libx264', '-preset', 'slow', '-crf', '27', '-pix_fmt', 'yuv420p', '-r', '25', '-movflags', '+faststart', ziel], check=True)


def main():
    args = sys.argv[1:]; themen = THEMEN
    if '--themen' in args: i = args.index('--themen'); themen = args[i + 1].split(','); del args[i:i + 2]
    sprachen = args or SPRACHEN
    js = "global.window={};require(%s);process.stdout.write(JSON.stringify(window.EKL_TEXTE))" % json.dumps(os.path.join(ROOT, 'texte.js'))
    TEXTE = json.loads(subprocess.run(['node', '-e', js], capture_output=True, text=True, check=True).stdout)
    info_pfad = os.path.join(OUT, 'info.json')
    try: info = json.load(open(info_pfad))
    except Exception: info = {}
    srv, BASE = server(); fehler = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        for sp in sprachen:
            os.makedirs(os.path.join(OUT, sp), exist_ok=True)
            hat_ton = stimme(sp) is not None
            if hat_ton: sprich(sp, sprechbar(sp, TEXTE[sp]['app_titel']))
            for th in themen:
                if hat_ton:   # Sprachaufnahmen VOR der Aufnahme erzeugen, sonst hinken die Untertitel hinterher
                    for zeile in TEXTE[sp]['v_' + th].split('|'): sprich(sp, sprechbar(sp, zeile))
                tmp = tempfile.mkdtemp(prefix='ekl_vid_')
                ctx = b.new_context(viewport={'width': W, 'height': H}, record_video_dir=tmp, record_video_size={'width': W, 'height': H},
                                    permissions=['clipboard-read', 'clipboard-write'], locale='de-DE')
                eintraege = [{'id': f'b{i}', 'a': a, 'x': a, 'm': m, 't': i + 1} for i, (a, m) in enumerate(BEISPIEL)]
                for e in eintraege:
                    if not e['m']: del e['m']
                eintraege.append({'id': 'b99', 'x': EIGEN[sp], 't': 99})
                saat = json.dumps({'v': 1, 'e': eintraege})
                ctx.add_init_script("try{if(!sessionStorage.getItem('saat')){sessionStorage.setItem('saat','1');localStorage.setItem('ekl_sprache','%s');localStorage.setItem('ekl_liste',%s);localStorage.setItem('ekl_install_weg','1');localStorage.setItem('ekl_thema','hell');}}catch(e){}" % (sp, json.dumps(saat)))
                ctx.add_init_script(INIT)
                pg = ctx.new_page(); errs = []
                pg.on('pageerror', lambda e: errs.append(str(e)))
                t_start = time.time()
                pg.goto(BASE); pg.wait_for_timeout(900)
                S.thema = th; s = S(pg, sp, TEXTE[sp]); s.t0 = t_start
                try: SZENEN[th](s); pg.evaluate('window.__cap("")'); pg.wait_for_timeout(500)
                except Exception as e: errs.append('Szene: ' + str(e)[:300])
                roh = pg.video.path(); ctx.close()
                ziel = os.path.join(OUT, sp, th + '.mp4'); trim = 0.8
                if s.ton: ton_einmischen(roh, s.ton, trim, ziel)
                else: ohne_ton(roh, trim, ziel)
                subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', '2.2', '-i', ziel, '-frames:v', '1', '-q:v', '4', os.path.join(OUT, sp, th + '.jpg')], check=True)
                shutil.rmtree(tmp, ignore_errors=True)
                dauer = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', ziel], capture_output=True, text=True).stdout or 0)
                print(f'{sp}/{th}: {os.path.getsize(ziel) // 1024} KB, {dauer:.0f} s, {len(s.ton)} Sprachstellen', ('FEHLER: ' + ' | '.join(errs)) if errs else 'ok', flush=True)
                if errs: fehler.append(f'{sp}/{th}')
            info[sp] = {'ton': hat_ton}
        b.close()
    srv.shutdown()
    json.dump(info, open(info_pfad, 'w'), indent=1, sort_keys=True)
    if fehler: print('Fehler bei:', ', '.join(fehler)); sys.exit(1)


if __name__ == '__main__':
    main()
