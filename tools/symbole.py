#!/usr/bin/env python3
"""Einkaufsliste – App-Symbole zeichnen (Zettel mit Häkchen, Rot/Weiß).
Aufruf: python3 tools/symbole.py   → icons/icon-192.png, icon-512.png, icon-maskable-512.png,
                                     apple-touch-icon.png (180), favicon-32.png, favicon.svg"""
import os
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, 'icons')
ROT = (226, 35, 42); WEISS = (255, 255, 255); GRAU = (226, 222, 216); TINTE = (40, 40, 40)
S = 4  # Überabtastung


def zeichnen(groesse, maskable=False, rund=True):
    g = groesse * S; img = Image.new('RGBA', (g, g), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    if maskable or not rund: d.rectangle([0, 0, g, g], fill=ROT)
    else: d.rounded_rectangle([0, 0, g - 1, g - 1], radius=int(g * 0.22), fill=ROT)
    k = 0.62 if maskable else 0.80          # maskable: Inhalt in der sicheren Mitte
    zw, zh = g * k * 0.72, g * k            # Zettel
    x0, y0 = (g - zw) / 2, (g - zh) / 2
    d.rounded_rectangle([x0, y0, x0 + zw, y0 + zh], radius=int(g * k * 0.07), fill=WEISS)
    # drei Zeilen: zwei abgehakt, eine offen
    zeilen = 3; rand = zw * 0.14; kreis = zw * 0.17; abst = (zh - 2 * rand) / zeilen
    for i in range(zeilen):
        cy = y0 + rand + abst * (i + 0.5); cx = x0 + rand + kreis / 2
        box = [cx - kreis / 2, cy - kreis / 2, cx + kreis / 2, cy + kreis / 2]
        lx0 = cx + kreis / 2 + zw * 0.09; lx1 = x0 + zw - rand
        lw = max(2, zw * 0.055)
        if i < 2:
            d.ellipse(box, fill=ROT)
            p = [(cx - kreis * 0.24, cy + kreis * 0.01), (cx - kreis * 0.05, cy + kreis * 0.2), (cx + kreis * 0.26, cy - kreis * 0.18)]
            d.line(p, fill=WEISS, width=int(kreis * 0.15), joint='curve')
            d.rounded_rectangle([lx0, cy - lw / 2, lx1 - zw * 0.12, cy + lw / 2], radius=lw / 2, fill=GRAU)
        else:
            d.ellipse(box, outline=TINTE, width=int(kreis * 0.12))
            d.rounded_rectangle([lx0, cy - lw / 2, lx1, cy + lw / 2], radius=lw / 2, fill=TINTE)
    return img.resize((groesse, groesse), Image.LANCZOS)


SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#E2232A"/>
<rect x="14.5" y="6.5" width="35" height="51" rx="3.5" fill="#fff"/>
<circle cx="21.5" cy="17" r="4" fill="#E2232A"/><path d="M19.6 17.1l1.4 1.4 2.6-2.8" stroke="#fff" stroke-width="1.6" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
<rect x="28" y="15.6" width="15" height="2.8" rx="1.4" fill="#E2DED8"/>
<circle cx="21.5" cy="32" r="4" fill="#E2232A"/><path d="M19.6 32.1l1.4 1.4 2.6-2.8" stroke="#fff" stroke-width="1.6" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
<rect x="28" y="30.6" width="15" height="2.8" rx="1.4" fill="#E2DED8"/>
<circle cx="21.5" cy="47" r="3.4" fill="none" stroke="#282828" stroke-width="1.3"/>
<rect x="28" y="45.6" width="17" height="2.8" rx="1.4" fill="#282828"/></svg>
"""

if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    zeichnen(192).save(os.path.join(OUT, 'icon-192.png'))
    zeichnen(512).save(os.path.join(OUT, 'icon-512.png'))
    zeichnen(512, maskable=True).save(os.path.join(OUT, 'icon-maskable-512.png'))
    zeichnen(180, rund=False).convert('RGB').save(os.path.join(OUT, 'apple-touch-icon.png'))
    zeichnen(32).save(os.path.join(OUT, 'favicon-32.png'))
    open(os.path.join(OUT, 'favicon.svg'), 'w').write(SVG)
    print('Symbole geschrieben nach', OUT)
