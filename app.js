/* Einkaufsliste – Programmlogik.
   Alles bleibt auf dem Gerät (localStorage, Schlüssel mit Präfix „ekl_“). Kein Server, keine Anmeldung.
   Katalogartikel werden mit fester Artikel-ID gespeichert (a = ID), eigene Einträge als Text (x).
   Datenformat ekl_liste: { v:1, e:[ { id, a?, x?, m?, d?, t, td? } ] }
     id = interne Nummer · a = Artikel-ID · x = Freitext (bei Katalogartikeln: Name beim Anlegen, nur Ersatz)
     m = Menge/Notiz · d = erledigt (im Wagen) · t = angelegt (ms) · td = abgehakt (ms) */
(function () {
"use strict";

const VERSION = "1.1.0";
const SPRACHEN = window.EKL_SPRACHEN.map(s => s.code);
const BEREICHE = ["lm", "hh", "kl"];
const HILFE_THEMEN = ["hinzufuegen", "katalog", "abhaken", "teilen", "installieren"];
const $ = id => document.getElementById(id);

// ───────────── Speicher (immer mit try/catch) ─────────────
let speicherOk = true;
function lesen(k, ersatz) {
  try { const v = localStorage.getItem(k); return v === null ? ersatz : v; } catch (e) { speicherOk = false; return ersatz; }
}
function schreiben(k, v) {
  try { localStorage.setItem(k, v); return true; } catch (e) { speicherOk = false; return false; }
}
try { const p = "ekl_probe"; localStorage.setItem(p, "1"); localStorage.removeItem(p); } catch (e) { speicherOk = false; }

// ───────────── Sprache ─────────────
function startSprache() {
  const gemerkt = lesen("ekl_sprache", "");
  if (SPRACHEN.includes(gemerkt)) return gemerkt;
  const wuensche = (navigator.languages && navigator.languages.length ? navigator.languages : [navigator.language || "de"]);
  for (const w of wuensche) {
    const c = String(w || "").toLowerCase().slice(0, 2);
    if (SPRACHEN.includes(c)) return c;
  }
  return "de";
}
let sprache = startSprache();
function t(k, werte) {
  const tab = window.EKL_TEXTE[sprache] || window.EKL_TEXTE.de;
  let s = (k in tab) ? tab[k] : (window.EKL_TEXTE.de[k] ?? k);
  if (werte) for (const [a, b] of Object.entries(werte)) s = s.split("{" + a + "}").join(b);
  return s;
}
function texteAnwenden() {
  document.documentElement.lang = sprache;
  document.querySelectorAll("[data-t]").forEach(el => { el.textContent = t(el.dataset.t); });
  document.querySelectorAll("[data-t-aria]").forEach(el => { el.setAttribute("aria-label", t(el.dataset.tAria)); el.title = t(el.dataset.tAria); });
  document.querySelectorAll("[data-t-platz]").forEach(el => { el.placeholder = t(el.dataset.tPlatz); });
  document.title = t("app_titel");
  $("spracheKurz").textContent = sprache.toUpperCase();
  $("versionText").textContent = t("version", { v: VERSION });
  $("einstVersion").textContent = t("version", { v: VERSION });
  $("ueberText").textContent = t("ueber_text", { firma: "Thomas Willwacher Fliesenlegermeister e.K.", ort: "Nisterau" });
  document.querySelectorAll('a[target="_blank"]').forEach(a => { a.title = t("neues_fenster"); });
  eingabePlatzhalter();
}

// Katalog einer Sprache bei Bedarf nachladen (de ist immer da)
const ladend = {};
function katalogLaden(code) {
  const N = window.EKL_KATALOG_NAMEN || {};
  if (N[code]) return Promise.resolve();
  if (ladend[code]) return ladend[code];
  ladend[code] = new Promise(ok => {
    const s = document.createElement("script");
    s.src = "katalog/" + code + ".js";
    s.onload = () => ok(); s.onerror = () => ok();   // fehlt die Datei: deutsche Namen als Ersatz
    document.head.appendChild(s);
  });
  return ladend[code];
}

// ───────────── Katalog-Index ─────────────
// ART: id -> { id, typ, hi, gi, pos, name, gruppe, abt, farbe }
let ART = new Map(), NAMEN_INDEX = new Map(), KAT = { lm: [], hh: [], kl: [] };
function norm(s) { return String(s || "").normalize("NFC").trim().toLowerCase().replace(/\s+/g, " "); }
function indexBauen() {
  const A = window.EKL_KATALOG_AUFBAU, N = window.EKL_KATALOG_NAMEN || {};
  const L = N[sprache] || N.de, D = N.de;
  ART = new Map(); NAMEN_INDEX = new Map(); KAT = { lm: [], hh: [], kl: [] };
  let pos = 0;
  for (const typ of BEREICHE) {
    (A[typ] || []).forEach((abt, hi) => {
      const ln = (L[typ] && L[typ][hi]) || D[typ][hi];
      const k = { name: ln[0], farbe: abt.farbe, gruppen: [] };
      abt.gruppen.forEach((ids, gi) => {
        const lg = ln[1][gi] || D[typ][hi][1][gi];
        const g = { name: lg[0], artikel: [] };
        ids.forEach((id, ai) => {
          const name = lg[1][ai] || D[typ][hi][1][gi][1][ai];
          const art = { id, typ, hi, gi, pos: pos++, name, gruppe: g.name, abt: k.name, farbe: abt.farbe };
          ART.set(id, art); g.artikel.push(art);
          const n = norm(name); if (!NAMEN_INDEX.has(n)) NAMEN_INDEX.set(n, id);
        });
        k.gruppen.push(g);
      });
      KAT[typ].push(k);
    });
  }
  // deutsche Namen zusätzlich erkennen (z. B. wenn jemand deutsch tippt oder eine deutsche Textliste einfügt)
  if (L !== D) for (const typ of BEREICHE) D[typ].forEach((abt, hi) => abt[1].forEach((g, gi) => g[1].forEach((name, ai) => {
    const n = norm(name); if (!NAMEN_INDEX.has(n)) NAMEN_INDEX.set(n, A[typ][hi].gruppen[gi][ai]);
  })));
}
function artikelZuText(text) {
  const n = norm(text);
  if (NAMEN_INDEX.has(n)) return NAMEN_INDEX.get(n);
  // Mehrzahl/Einzahl grob tolerieren (Mango ↔ Mangos, Apple ↔ Apples)
  for (const v of [n + "s", n.replace(/s$/, ""), n + "n", n.replace(/n$/, ""), n + "e", n.replace(/e$/, "")])
    if (v !== n && NAMEN_INDEX.has(v)) return NAMEN_INDEX.get(v);
  return null;
}

// Eigene Einträge (Freitext) trotzdem einer passenden Abteilung zuordnen – nur für die Sortierung,
// der Text bleibt so, wie er getippt wurde. „Milch“ → wie „Vollmilch“, „Hackfleisch“ → wie „Hackfleisch gemischt“.
const ratenCache = new Map();
function abteilungRaten(text) {
  const q = norm(text); if (q.length < 3) return null;
  const k = sprache + "|" + q; if (ratenCache.has(k)) return ratenCache.get(k);
  let best = null;
  for (const a of ART.values()) {
    const n = norm(a.name);
    if (n === q || n.startsWith(q + " ") || n.endsWith(" " + q) || (q.length >= 4 && n.endsWith(q))) { if (!best || a.pos < best.pos) best = a; }
  }
  ratenCache.set(k, best); return best;
}

// ───────────── Liste ─────────────
let eintraege = [];
function listeLaden() {
  try {
    const roh = JSON.parse(lesen("ekl_liste", "") || "null");
    if (roh && Array.isArray(roh.e)) eintraege = roh.e.filter(e => e && e.id && (e.a || e.x));
  } catch (e) { eintraege = []; }
}
function listeSpeichern() { schreiben("ekl_liste", JSON.stringify({ v: 1, e: eintraege })); }
function neueId() { return Date.now().toString(36) + Math.random().toString(36).slice(2, 7); }
function anzeigeName(e) { const a = e.a && ART.get(e.a); return a ? a.name : (e.x || e.a || ""); }
function schluessel(e) { return e.a ? "a:" + e.a : "x:" + norm(e.x); }
function offenGleich(eintrag) { const k = schluessel(eintrag); return eintraege.find(e => !e.d && schluessel(e) === k); }

// Menge vorne abtrennen: „2 Milch“, „500 g Hackfleisch“, „3x Joghurt“, „1,5 kg Kartoffeln“
const EINHEITEN = "x|stk|stück|st|g|gr|kg|mg|l|ltr|liter|litre|ml|cl|dl|pck|pkg|packung|packungen|pack|packs|pc|pcs|dose|dosen|can|cans|tin|tins|flasche|flaschen|bottle|bottles|becher|bund|glas|gläser|jar|jars|tüte|tüten|beutel|bag|bags|scheiben|ks|kus|kusy|kusů|bal|balení|balenie|láhev|lahve|fľaša|fľaše|plechovka|plechovky|sáček|sáčky|vrecko|szt|sztuk|opak|opakowanie|opakowania|butelka|butelki|puszka|puszki|słoik|słoiki|paczka|paczki|шт|штук|уп|упаковка|упаковки|пляшка|пляшки|банка|банки|пачка|пачки|г|кг|л|мл";
const MENGE_RE = new RegExp("^((?:\\d+(?:[.,]\\d+)?|½|¼|¾)\\s*(?:(?:" + EINHEITEN + ")\\.?)?)\\s+(.+)$", "iu");
function eingabeZerlegen(s) {
  s = String(s || "").trim().replace(/\s+/g, " ");
  const m = s.match(MENGE_RE);
  if (m && m[2].trim()) return { name: m[2].trim(), menge: m[1].trim() };
  return { name: s, menge: "" };
}

function hinzufuegen(name, menge, still) {
  name = String(name || "").trim(); if (!name) return null;
  const aid = artikelZuText(name);
  const neu = aid ? { id: neueId(), a: aid, x: ART.get(aid).name, t: Date.now() } : { id: neueId(), x: name.slice(0, 80), t: Date.now() };
  if (menge) neu.m = String(menge).slice(0, 40);
  const da = offenGleich(neu);
  if (da) {
    if (menge && !da.m) { da.m = neu.m; listeSpeichern(); zeichnen(); }
    if (!still) zeigeToast(t("toast_schon", { name: anzeigeName(da) }));
    return da;
  }
  eintraege.push(neu); listeSpeichern(); frisch = neu.id;
  zeichnen();
  return neu;
}
function loeschen(id) {
  const i = eintraege.findIndex(e => e.id === id); if (i < 0) return;
  const alt = eintraege[i]; eintraege.splice(i, 1); listeSpeichern(); zeichnen();
  zeigeToast(t("toast_entfernt", { name: anzeigeName(alt) }), () => { eintraege.splice(Math.min(i, eintraege.length), 0, alt); listeSpeichern(); zeichnen(); });
}
function umschalten(id) {
  const e = eintraege.find(x => x.id === id); if (!e) return;
  e.d = !e.d; if (e.d) e.td = Date.now(); else delete e.td;
  listeSpeichern(); zeichnen();
  try { navigator.vibrate && navigator.vibrate(12); } catch (x) {}
}
function aufraeumen() {
  const weg = eintraege.filter(e => e.d); if (!weg.length) return;
  const sicherung = eintraege.slice();
  eintraege = eintraege.filter(e => !e.d); listeSpeichern(); zeichnen();
  zeigeToast(t("toast_aufgeraeumt", { n: weg.length }), () => { eintraege = sicherung; listeSpeichern(); zeichnen(); });
}

// ───────────── Darstellung ─────────────
let aktiverTab = "liste", frisch = null;
const breit = window.matchMedia("(min-width: 1000px)");
function katalogTab() { return aktiverTab !== "liste" ? aktiverTab : (breit.matches ? letzterKatalog : null); }
let letzterKatalog = "lm";
function esc(s) { return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
const SYM = {
  haken: '<svg class="sym" viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12.5 4.5 4.5L19 7.5"/></svg>',
  stift: '<svg class="sym" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16v4z"/><path d="m13.5 6.5 4 4"/></svg>',
  kreuz: '<svg class="sym" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 7l10 10M17 7 7 17"/></svg>',
  pfeil: '<svg class="sym pfeil" viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>',
  plus: '<svg class="sym" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>'
};
function punkt(f) { return `<span class="punkt" style="--f:${esc(f)}" aria-hidden="true"></span>`; }

function zeile(e) {
  const name = anzeigeName(e);
  return `<li class="eintrag${e.d ? " erledigt" : ""}${frisch === e.id ? " neu-markiert" : ""}" data-id="${esc(e.id)}">
    <button type="button" class="eintrag-haupt" data-umschalten aria-pressed="${e.d ? "true" : "false"}" aria-label="${esc(name)}${e.m ? ", " + esc(e.m) : ""} – ${esc(t(e.d ? "aria_wieder_offen" : "aria_abhaken"))}">
      <span class="haken" aria-hidden="true">${SYM.haken}</span>
      <span class="eintrag-text"><span class="eintrag-name">${esc(name)}</span>${e.m ? `<span class="eintrag-menge">${esc(e.m)}</span>` : ""}</span>
    </button>
    ${e.d ? "" : `<button type="button" class="icon-knopf" data-bearbeiten aria-label="${esc(t("aria_bearbeiten"))}" title="${esc(t("aria_bearbeiten"))}">${SYM.stift}</button>`}
    <button type="button" class="icon-knopf" data-loeschen aria-label="${esc(t("aria_loeschen"))}" title="${esc(t("aria_loeschen"))}">${SYM.kreuz}</button>
  </li>`;
}

function zeichnen() {
  const offen = eintraege.filter(e => !e.d), erledigt = eintraege.filter(e => e.d).sort((a, b) => (b.td || 0) - (a.td || 0));
  $("tabZahl").textContent = offen.length; $("tabZahl").hidden = !offen.length;
  $("offenZahl").textContent = offen.length ? t("offen_zahl", { n: offen.length }) : "";
  document.title = (offen.length ? "(" + offen.length + ") " : "") + t("app_titel");

  const zeigeListe = aktiverTab === "liste" || breit.matches;
  $("ansichtListe").hidden = !zeigeListe;
  $("ansichtKatalog").hidden = !katalogTab();

  // Liste: offene nach Abteilungen in Laufrichtung
  const bloecke = new Map();
  for (const e of offen) {
    const a = (e.a && ART.get(e.a)) || (!e.a && abteilungRaten(e.x));
    const key = a ? a.typ + "|" + a.hi : "sonst";
    if (!bloecke.has(key)) bloecke.set(key, a ? { titel: a.abt, farbe: a.farbe, rang: BEREICHE.indexOf(a.typ) * 1000 + a.hi, liste: [] } : { titel: t("sonstiges"), farbe: "#9A948C", rang: 99999, liste: [] });
    bloecke.get(key).liste.push([e, a ? a.pos + 0.5 : 1e9]);
  }
  let html = "";
  for (const b of [...bloecke.values()].sort((x, y) => x.rang - y.rang)) {
    b.liste.sort((x, y) => x[1] - y[1] || x[0].t - y[0].t);
    html += `<div class="abschnitt"><span class="abschnitt-titel">${punkt(b.farbe)}<span>${esc(b.titel)}</span></span></div><ul class="liste">${b.liste.map(([e]) => zeile(e)).join("")}</ul>`;
  }
  $("offenBereich").innerHTML = html;
  $("listeErledigt").innerHTML = erledigt.map(zeile).join("");
  $("wagenText").textContent = t("im_wagen", { n: erledigt.length });
  $("wagenKopf").hidden = !erledigt.length;
  $("leer").hidden = eintraege.length !== 0;
  document.querySelector("#ansichtListe .leiste").hidden = eintraege.length === 0;
  if (!eintraege.length) $("startChips").innerHTML = START_ARTIKEL.filter(id => ART.has(id)).map(id => `<button type="button" class="chip" data-start="${id}">${SYM.plus}<span>${esc(ART.get(id).name)}</span></button>`).join("");
  $("btnTeilen").disabled = !offen.length && !eintraege.length;
  installKarteZeigen();
  frisch = null;

  if (katalogTab()) katalogZeichnen(offen);
}

function katalogZeichnen(offen) {
  const tab = katalogTab();
  const offeneIds = new Set(offen.filter(e => e.a).map(e => e.a));
  const chip = a => `<button type="button" class="chip${offeneIds.has(a.id) ? " drauf" : ""}" data-aid="${esc(a.id)}" aria-pressed="${offeneIds.has(a.id)}">${SYM.haken}<span>${esc(a.name)}</span></button>`;
  const suche = (aktiverTab !== "liste" || breit.matches) ? norm($("eingabe").value) : "";
  $("katHinweis").hidden = !!suche;
  if (suche) {
    const woerter = eingabeZerlegen(suche).name.split(" ").filter(Boolean);
    const treffer = [...ART.values()].filter(a => { const s = norm(a.name + " " + a.gruppe + " " + a.abt); return woerter.every(w => s.includes(w)); })
      .sort((x, y) => (x.typ !== tab) - (y.typ !== tab) || x.pos - y.pos);
    const gruppen = new Map();
    for (const a of treffer) { const k = a.typ + "|" + a.hi + "|" + a.gi; if (!gruppen.has(k)) gruppen.set(k, { a, liste: [] }); gruppen.get(k).liste.push(a); }
    $("katalog").innerHTML = `<div class="suchkopf"><span>${esc(t("treffer", { n: treffer.length }))}</span><button type="button" class="knopf zweit" data-suche-weg>${esc(t("suche_loeschen"))}</button></div>` +
      (treffer.length ? [...gruppen.values()].map(({ a, liste }) =>
        `<div class="treffer"><div class="pfad">${punkt(a.farbe)}${a.typ !== tab ? esc(t("tab_" + a.typ)) + " › " : ""}<b>${esc(a.abt)}</b> › ${esc(a.gruppe)}</div><div class="chips">${liste.map(chip).join("")}</div></div>`).join("")
        : `<div class="leer"><strong>${esc(t("nicht_im_katalog"))}</strong><span>${esc(t("nicht_im_katalog_2"))}</span></div>`);
    return;
  }
  const offenGeklappt = new Set([...document.querySelectorAll("details.kat[open]")].map(d => d.dataset.kat));
  $("katalog").innerHTML = KAT[tab].map((k, hi) => {
    const alle = k.gruppen.flatMap(g => g.artikel), drauf = alle.filter(a => offeneIds.has(a.id)).length, key = tab + "|" + hi;
    return `<details class="kat" data-kat="${key}"${offenGeklappt.has(key) ? " open" : ""}>
      <summary class="kat-kopf">${punkt(k.farbe)}<span class="kat-name">${esc(k.name)}</span>${drauf ? `<span class="kat-drauf" aria-label="${esc(t("vorschlag_drauf"))}: ${drauf}">${drauf}</span>` : ""}<span class="kat-zahl">${alle.length}</span>${SYM.pfeil}</summary>
      ${k.gruppen.map(g => (k.gruppen.length > 1 ? `<div class="gruppe">${esc(g.name)}</div>` : "") + `<div class="chips">${g.artikel.map(chip).join("")}</div>`).join("")}
    </details>`;
  }).join("");
}

// ───────────── Eingabe & Vorschläge ─────────────
function eingabePlatzhalter() {
  const tab = aktiverTab;
  $("eingabe").placeholder = (tab === "liste" || breit.matches) ? t("eingabe_platz") : t("such_" + tab);
}
function vorschlaegeZeigen() {
  const box = $("vorschlaege"), roh = $("eingabe").value;
  $("eingabeLeeren").hidden = !roh;
  const { name, menge } = eingabeZerlegen(roh);
  const q = norm(name);
  if (!(aktiverTab === "liste" || breit.matches) || q.length < 1) { box.hidden = true; $("eingabe").setAttribute("aria-expanded", "false"); return; }
  const offeneIds = new Set(eintraege.filter(e => !e.d && e.a).map(e => e.a));
  const liste = [];
  for (const a of ART.values()) {
    const n = norm(a.name);
    let rang = -1;
    if (n.startsWith(q)) rang = 0; else if (n.split(/[\s\-–(]+/).some(w => w.startsWith(q))) rang = 1; else if (q.length >= 3 && n.includes(q)) rang = 2;
    if (rang >= 0) liste.push([rang, n.length, a]);
  }
  liste.sort((x, y) => x[0] - y[0] || x[1] - y[1] || x[2].pos - y[2].pos);
  const top = liste.slice(0, 6).map(x => x[2]);
  const exakt = top.some(a => norm(a.name) === q);
  const markieren = s => { const i = norm(s).indexOf(q); return i < 0 ? esc(s) : esc(s.slice(0, i)) + "<mark>" + esc(s.slice(i, i + q.length)) + "</mark>" + esc(s.slice(i + q.length)); };
  let html = top.map((a, i) => `<button type="button" class="vorschlag" role="option" data-vorschlag="${esc(a.id)}" id="vs${i}">${punkt(a.farbe)}<span class="v-name">${markieren(a.name)}${menge ? ` <span class="v-abt">· ${esc(menge)}</span>` : ""}</span>${offeneIds.has(a.id) ? `<span class="v-drauf">${esc(t("vorschlag_drauf"))}</span>` : `<span class="v-abt">${esc(a.abt)}</span>`}</button>`).join("");
  if (!exakt && name.length >= 2) html += `<button type="button" class="vorschlag eigen" role="option" data-eigen>${SYM.plus}<span class="v-name">${esc(t("vorschlag_eigen", { text: name }))}</span></button>`;
  box.innerHTML = html; box.hidden = !html;
  $("eingabe").setAttribute("aria-expanded", html ? "true" : "false");
}
function eingabeLeeren() { $("eingabe").value = ""; $("vorschlaege").hidden = true; $("eingabeLeeren").hidden = true; $("eingabe").setAttribute("aria-expanded", "false"); }

$("formNeu").addEventListener("submit", ev => {
  ev.preventDefault();
  const { name, menge } = eingabeZerlegen($("eingabe").value);
  if (!name) return;
  hinzufuegen(name, menge);
  eingabeLeeren(); $("eingabe").focus();
  if (katalogTab()) zeichnen();
});
$("eingabe").addEventListener("input", () => { vorschlaegeZeigen(); if (katalogTab()) zeichnen(); });
$("eingabe").addEventListener("keydown", ev => {
  const box = $("vorschlaege"); const knoepfe = [...box.querySelectorAll(".vorschlag")];
  if (ev.key === "Escape") { box.hidden = true; return; }
  if ((ev.key === "ArrowDown" || ev.key === "ArrowUp") && knoepfe.length && !box.hidden) {
    ev.preventDefault();
    let i = knoepfe.findIndex(k => k.classList.contains("aktiv"));
    knoepfe.forEach(k => k.classList.remove("aktiv"));
    i = ev.key === "ArrowDown" ? (i + 1) % knoepfe.length : (i <= 0 ? knoepfe.length - 1 : i - 1);
    knoepfe[i].classList.add("aktiv"); $("eingabe").setAttribute("aria-activedescendant", knoepfe[i].id || "");
  }
  if (ev.key === "Enter") { const a = box.hidden ? null : box.querySelector(".vorschlag.aktiv"); if (a) { ev.preventDefault(); a.click(); } }
});
$("eingabeLeeren").addEventListener("click", () => { eingabeLeeren(); zeichnen(); $("eingabe").focus(); });
$("vorschlaege").addEventListener("click", ev => {
  const b = ev.target.closest(".vorschlag"); if (!b) return;
  const { name, menge } = eingabeZerlegen($("eingabe").value);
  if (b.dataset.vorschlag) hinzufuegen(ART.get(b.dataset.vorschlag).name, menge); else hinzufuegen(name, menge);
  eingabeLeeren(); $("eingabe").focus(); if (katalogTab()) zeichnen();
});
document.addEventListener("click", ev => { if (!ev.target.closest(".eingabe")) $("vorschlaege").hidden = true; });

function listenKlick(ev) {
  const li = ev.target.closest("li[data-id]"); if (!li) return;
  const id = li.dataset.id;
  if (ev.target.closest("[data-loeschen]")) return loeschen(id);
  if (ev.target.closest("[data-bearbeiten]")) return bearbeitenOeffnen(id);
  if (ev.target.closest("[data-umschalten]")) return umschalten(id);
}
$("offenBereich").addEventListener("click", listenKlick);
$("listeErledigt").addEventListener("click", listenKlick);
$("btnAufraeumen").addEventListener("click", aufraeumen);
const START_ARTIKEL = ["vollmilch", "brot", "eier", "butter", "aepfel", "kaffee"];
$("startChips").addEventListener("click", ev => { const c = ev.target.closest("[data-start]"); if (c) hinzufuegen(ART.get(c.dataset.start).name, "", true); });

$("katalog").addEventListener("click", ev => {
  if (ev.target.closest("[data-suche-weg]")) { eingabeLeeren(); zeichnen(); return; }
  const c = ev.target.closest(".chip[data-aid]"); if (!c) return;
  const aid = c.dataset.aid, da = eintraege.find(e => !e.d && e.a === aid);
  if (da) loeschen(da.id); else { const a = ART.get(aid); hinzufuegen(a.name, "", true); }
});

$("tabs").addEventListener("click", ev => {
  const b = ev.target.closest("button[data-tab]"); if (!b) return;
  tabWechseln(b.dataset.tab);
});
function tabWechseln(tab) {
  aktiverTab = tab; if (tab !== "liste") letzterKatalog = tab;
  if (breit.matches && tab === "liste") aktiverTab = letzterKatalog;
  for (const x of $("tabs").children) { const an = x.dataset.tab === aktiverTab; x.classList.toggle("aktiv", an); if (an) x.setAttribute("aria-current", "page"); else x.removeAttribute("aria-current"); }
  eingabePlatzhalter(); $("vorschlaege").hidden = true;
  zeichnen(); if (!breit.matches) window.scrollTo(0, 0);
}
breit.addEventListener ? breit.addEventListener("change", () => tabWechseln(aktiverTab)) : breit.addListener(() => tabWechseln(aktiverTab));

// ───────────── Toast ─────────────
let toastUhr;
function zeigeToast(text, rueck) {
  $("toastText").textContent = text;
  $("toastAktion").hidden = !rueck;
  $("toastAktion").onclick = () => { $("toast").hidden = true; rueck && rueck(); };
  $("toast").hidden = false;
  clearTimeout(toastUhr); toastUhr = setTimeout(() => { $("toast").hidden = true; }, rueck ? 6000 : 3500);
}

// ───────────── Fenster ─────────────
let fensterZurueck = [];
function fensterAuf(id) {
  const f = $(id); fensterZurueck.push(document.activeElement);
  f.hidden = false;
  const ziel = f.querySelector("[autofocus]") || f.querySelector(".fenster-inhalt input, .fenster-inhalt button, .fenster-inhalt textarea, .kreuz-knopf");
  setTimeout(() => ziel && ziel.focus({ preventScroll: true }), 30);
}
function fensterZu(id) {
  const f = $(id); if (f.hidden) return;
  f.hidden = true; f.querySelectorAll("video").forEach(v => { try { v.pause(); } catch (e) {} });
  const z = fensterZurueck.pop(); if (z && z.focus) z.focus({ preventScroll: true });
}
document.querySelectorAll(".fenster").forEach(f => {
  f.addEventListener("click", ev => { if (ev.target === f || ev.target.closest("[data-zu]")) fensterZu(f.id); });
});
document.addEventListener("keydown", ev => {
  if (ev.key !== "Escape") return;
  const offen = [...document.querySelectorAll(".fenster:not([hidden])")].pop(); if (offen) fensterZu(offen.id);
});

// Bearbeiten (Menge/Notiz)
let bearbId = null;
function bearbeitenOeffnen(id) {
  const e = eintraege.find(x => x.id === id); if (!e) return;
  bearbId = id; $("bearbName").value = anzeigeName(e); $("bearbMenge").value = e.m || "";
  $("mengenChips").innerHTML = t("menge_vorschlaege").split("|").map(m => `<button type="button" class="chip" data-menge="${esc(m)}">${esc(m)}</button>`).join("");
  fensterAuf("dlgBearb");
  setTimeout(() => $("bearbMenge").focus(), 40);
}
$("mengenChips").addEventListener("click", ev => { const c = ev.target.closest("[data-menge]"); if (c) { $("bearbMenge").value = c.dataset.menge; $("bearbMenge").focus(); } });
$("formBearb").addEventListener("submit", ev => {
  ev.preventDefault();
  const e = eintraege.find(x => x.id === bearbId); if (!e) return fensterZu("dlgBearb");
  const name = $("bearbName").value.trim(), menge = $("bearbMenge").value.trim();
  if (name && name !== anzeigeName(e)) {
    const aid = artikelZuText(name);
    if (aid) { e.a = aid; e.x = ART.get(aid).name; } else { delete e.a; e.x = name.slice(0, 80); }
  }
  if (menge) e.m = menge.slice(0, 40); else delete e.m;
  listeSpeichern(); zeichnen(); fensterZu("dlgBearb");
});

// ───────────── Teilen ─────────────
function b64url(bytes) { let s = ""; for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000)); return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, ""); }
function b64urlZuBytes(s) { s = s.replace(/-/g, "+").replace(/_/g, "/"); while (s.length % 4) s += "="; const b = atob(s); const u = new Uint8Array(b.length); for (let i = 0; i < b.length; i++) u[i] = b.charCodeAt(i); return u; }
async function strom(bytes, art, aufbau) { const s = new Blob([bytes]).stream().pipeThrough(aufbau ? new CompressionStream(art) : new DecompressionStream(art)); return new Uint8Array(await new Response(s).arrayBuffer()); }
// Inhalt: je Zeile „a:<Artikel-ID>“ oder „x:<Freitext>“, optional Tab + Menge
function listeKodieren(liste) {
  return liste.map(e => (e.a ? "a:" + e.a : "x:" + String(e.x).replace(/[\t\n\r]/g, " ")) + (e.m ? "\t" + String(e.m).replace(/[\t\n\r]/g, " ") : "")).join("\n");
}
async function linkErzeugen() {
  const offen = eintraege.filter(e => !e.d);
  const roh = new TextEncoder().encode(listeKodieren(offen));
  let code = "t" + b64url(roh);
  if (typeof CompressionStream === "function") {
    try { const z = "z" + b64url(await strom(roh, "deflate-raw", true)); if (z.length < code.length) code = z; } catch (e) {}
  }
  return location.origin + location.pathname + "#liste=" + code;
}
async function linkLesen(code) {
  const art = code[0], daten = b64urlZuBytes(code.slice(1));
  let bytes;
  if (art === "z") { if (typeof DecompressionStream !== "function") throw new Error("alt"); bytes = await strom(daten, "deflate-raw", false); }
  else if (art === "t") bytes = daten; else throw new Error("format");
  const text = new TextDecoder().decode(bytes), liste = [];
  for (const zeile of text.split("\n")) {
    if (!zeile) continue;
    const [kopf, menge] = zeile.split("\t");
    if (kopf.startsWith("a:")) liste.push({ a: kopf.slice(2), m: menge || "" });
    else if (kopf.startsWith("x:") && kopf.length > 2) liste.push({ x: kopf.slice(2).slice(0, 80), m: menge || "" });
  }
  return liste;
}
function textErzeugen() {
  const offen = eintraege.filter(e => !e.d), bloecke = new Map();
  for (const e of offen) {
    const a = (e.a && ART.get(e.a)) || (!e.a && abteilungRaten(e.x)); const key = a ? a.typ + "|" + a.hi : "sonst";
    if (!bloecke.has(key)) bloecke.set(key, { titel: a ? a.abt : t("sonstiges"), rang: a ? BEREICHE.indexOf(a.typ) * 1000 + a.hi : 99999, liste: [] });
    bloecke.get(key).liste.push([anzeigeName(e) + (e.m ? " (" + e.m + ")" : ""), a ? a.pos : 1e9]);
  }
  let s = t("app_titel") + "\n";
  for (const b of [...bloecke.values()].sort((x, y) => x.rang - y.rang)) {
    s += "\n" + b.titel + "\n" + b.liste.sort((x, y) => x[1] - y[1]).map(x => "- " + x[0]).join("\n") + "\n";
  }
  return s.trim();
}
function textLesen(text) {
  const zeilen = text.split(/\r?\n/).map(z => z.trim()).filter(Boolean);
  const mitStrich = zeilen.filter(z => /^[-–•*·]\s*/.test(z));
  const quelle = mitStrich.length ? mitStrich : zeilen.filter(z => !Object.values(window.EKL_TEXTE).some(T => norm(T.app_titel) === norm(z)));
  return quelle.map(z => {
    z = z.replace(/^[-–•*·]\s*/, "").replace(/^\[[ x]?\]\s*/i, "");
    const m = z.match(/^(.*?)\s*\(([^()]{1,40})\)\s*$/);
    const teil = m ? { name: m[1], menge: m[2] } : eingabeZerlegen(z);
    const aid = artikelZuText(teil.name);
    return aid ? { a: aid, m: teil.menge } : { x: teil.name.slice(0, 80), m: teil.menge };
  }).filter(e => e.a || e.x);
}
async function teilenAusfuehren(daten, meldungOk) {
  const feld = $("teilenFeld");
  if (navigator.share) {
    try { await navigator.share(daten); return; } catch (e) { if (e && e.name === "AbortError") return; }
  }
  const inhalt = daten.url ? daten.url : daten.text;
  feld.value = inhalt; $("teilenErgebnis").hidden = false;
  try {
    await navigator.clipboard.writeText(inhalt);
    $("teilenMeldung").textContent = meldungOk;
  } catch (e) {
    $("teilenMeldung").textContent = t("kopieren_selbst");
    feld.focus(); feld.select();
  }
}
$("btnTeilen").addEventListener("click", () => {
  const offen = eintraege.filter(e => !e.d).length;
  $("teilenLeer").hidden = !!offen; $("btnLinkTeilen").disabled = !offen; $("btnTextTeilen").disabled = !offen;
  $("teilenErgebnis").hidden = true; $("empfangenFeld").value = "";
  fensterAuf("dlgTeilen");
});
$("btnLinkTeilen").addEventListener("click", async () => {
  const url = await linkErzeugen();
  teilenAusfuehren({ title: t("app_titel"), text: t("teilen_nachricht"), url }, t("kopiert_link"));
});
$("btnTextTeilen").addEventListener("click", () => teilenAusfuehren({ title: t("app_titel"), text: textErzeugen() }, t("kopiert_text")));
$("btnEmpfangen").addEventListener("click", async () => {
  const roh = $("empfangenFeld").value.trim(); if (!roh) return;
  const m = roh.match(/#liste=([A-Za-z0-9_\-]+)/);
  fensterZu("dlgTeilen");
  if (m) await importStarten(m[1]); else importZeigen(textLesen(roh));
});

// Empfangen: Link mit #liste=… beim Öffnen
let importDaten = [];
async function importStarten(code) {
  try { importZeigen(await linkLesen(code)); }
  catch (e) { zeigeToast(t("import_fehler")); }
}
function importZeigen(liste) {
  // innerhalb der geteilten Liste doppelte zusammenfassen
  const gesehen = new Map();
  for (const e of liste) {
    if (e.a && !ART.has(e.a)) continue;                     // unbekannte ID (älterer/neuerer Katalog) → überspringen
    const k = e.a ? "a:" + e.a : "x:" + norm(e.x);
    if (!gesehen.has(k)) gesehen.set(k, e); else if (e.m && !gesehen.get(k).m) gesehen.get(k).m = e.m;
  }
  importDaten = [...gesehen.values()];
  if (!importDaten.length) { zeigeToast(t("import_leer")); return; }
  $("importListe").innerHTML = importDaten.map(e => {
    const a = e.a && ART.get(e.a), name = a ? a.name : e.x, da = offenGleich(e);
    return `<li>${punkt(a ? a.farbe : "#9A948C")}<span>${esc(name)}${da ? ` <span class="i-da">· ${esc(t("vorschlag_drauf"))}</span>` : ""}</span>${e.m ? `<span class="i-menge">${esc(e.m)}</span>` : ""}</li>`;
  }).join("");
  fensterAuf("dlgImport");
}
function hashEntfernen() { if (location.hash) history.replaceState(null, "", location.pathname + location.search); }
$("btnImportJa").addEventListener("click", () => {
  let neu = 0, da = 0;
  for (const e of importDaten) {
    const vorh = offenGleich(e);
    if (vorh) { da++; if (e.m && !vorh.m) vorh.m = e.m; continue; }
    const x = { id: neueId(), t: Date.now() };
    if (e.a) { x.a = e.a; x.x = ART.get(e.a).name; } else x.x = e.x;
    if (e.m) x.m = e.m;
    eintraege.push(x); neu++;
  }
  listeSpeichern(); importDaten = []; hashEntfernen(); fensterZu("dlgImport");
  tabWechseln("liste"); zeigeToast(t("import_ergebnis", { neu, da }));
});
$("btnImportNein").addEventListener("click", () => { importDaten = []; hashEntfernen(); fensterZu("dlgImport"); });
$("dlgImport").addEventListener("click", ev => { if (ev.target === $("dlgImport") || ev.target.closest("[data-zu]")) hashEntfernen(); });
function hashPruefen() {
  const m = location.hash.match(/^#liste=([A-Za-z0-9_\-]+)/);
  if (m) importStarten(m[1]);
}
window.addEventListener("hashchange", hashPruefen);

// ───────────── Sprache & Einstellungen ─────────────
function sprachListeZeichnen() {
  const html = window.EKL_SPRACHEN.map(s => `<button type="button" class="sprach-wahl" role="radio" lang="${s.code}" data-sprache="${s.code}" aria-checked="${s.code === sprache}"><span>${esc(s.name)}</span><small>${s.code.toUpperCase()}</small></button>`).join("");
  $("spracheListe1").innerHTML = html; $("spracheListe2").innerHTML = html;
}
async function spracheSetzen(code) {
  if (!SPRACHEN.includes(code)) return;
  await katalogLaden(code);
  sprache = code; schreiben("ekl_sprache", code);
  indexBauen(); texteAnwenden(); sprachListeZeichnen(); hilfeZeichnen(); einstInstallZeichnen(); zeichnen();
}
document.addEventListener("click", ev => {
  const b = ev.target.closest("[data-sprache]"); if (!b) return;
  spracheSetzen(b.dataset.sprache).then(() => { if (!$("dlgSprache").hidden) fensterZu("dlgSprache"); });
});
$("btnSprache").addEventListener("click", () => { sprachListeZeichnen(); fensterAuf("dlgSprache"); });
$("btnEinst").addEventListener("click", () => { sprachListeZeichnen(); themaKnoepfe(); einstInstallZeichnen(); fensterAuf("dlgEinst"); });

function themaSetzen(th) {
  if (th === "hell" || th === "dunkel") document.documentElement.setAttribute("data-theme", th); else document.documentElement.removeAttribute("data-theme");
  schreiben("ekl_thema", th); themaKnoepfe(); themaFarbe();
}
function themaKnoepfe() {
  const th = lesen("ekl_thema", "auto");
  $("themaWahl").querySelectorAll("[data-thema]").forEach(b => b.setAttribute("aria-checked", b.dataset.thema === (th === "hell" || th === "dunkel" ? th : "auto")));
}
function themaFarbe() {
  const m = document.querySelector('meta[name="theme-color"]'); if (m) m.content = "#1f7a4d";
}
$("themaWahl").addEventListener("click", ev => { const b = ev.target.closest("[data-thema]"); if (b) themaSetzen(b.dataset.thema); });

// ───────────── Installieren ─────────────
let installAufforderung = null;
const istIos = /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
function istInstalliert() { try { return window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true; } catch (e) { return false; } }
window.addEventListener("beforeinstallprompt", ev => { ev.preventDefault(); installAufforderung = ev; installKarteZeigen(); einstInstallZeichnen(); });
window.addEventListener("appinstalled", () => { installAufforderung = null; schreiben("ekl_install_weg", "1"); installKarteZeigen(); einstInstallZeichnen(); zeigeToast(t("install_fertig")); });
function installMoeglich() { return !istInstalliert() && (installAufforderung || istIos); }
function installKarteZeigen() { $("installKarte").hidden = !installMoeglich() || lesen("ekl_install_weg", "") === "1"; }
async function installieren() {
  if (installAufforderung) {
    const a = installAufforderung;
    try { await a.prompt(); const w = await a.userChoice; if (w && w.outcome === "accepted") { installAufforderung = null; schreiben("ekl_install_weg", "1"); } } catch (e) {}
    installKarteZeigen(); einstInstallZeichnen();
  } else if (istIos) fensterAuf("dlgIos");
}
function einstInstallZeichnen() {
  const box = $("einstInstall");
  if (istInstalliert()) box.innerHTML = `<p class="klein-text">${esc(t("install_schon"))}</p>`;
  else if (installAufforderung) box.innerHTML = `<p class="klein-text">${esc(t("install_text"))}</p><button type="button" class="knopf haupt-knopf breit-knopf" data-installieren>${esc(t("install_knopf"))}</button>`;
  else if (istIos) box.innerHTML = `<p class="klein-text">${esc(t("install_text"))}</p><button type="button" class="knopf haupt-knopf breit-knopf" data-installieren>${esc(t("install_ios_titel"))}</button>`;
  else box.innerHTML = `<p class="klein-text">${esc(t("install_text"))}</p><p class="klein-text">${esc(t("install_anders"))}</p>`;
}
document.addEventListener("click", ev => { if (ev.target.closest("[data-installieren]")) installieren(); });
$("btnInstallKarte").addEventListener("click", installieren);
$("btnInstallWeg").addEventListener("click", () => { schreiben("ekl_install_weg", "1"); installKarteZeigen(); });

// ───────────── Hilfe ─────────────
let videoInfo = null;
function lautstaerke() { const v = parseInt(lesen("ekl_lautstaerke", "80"), 10); return isNaN(v) ? 80 : Math.max(0, Math.min(100, v)); }
function hilfeZeichnen() {
  const ohneTon = videoInfo && videoInfo[sprache] && videoInfo[sprache].ton === false;
  const offen = $("hilfeThemen").querySelector("details[open]");
  const offenId = offen ? offen.dataset.thema : null;
  $("hilfeThemen").innerHTML = HILFE_THEMEN.map((id, i) => `
    <details class="hilfe-thema" data-thema="${id}"${offenId === id ? " open" : ""}>
      <summary><span class="nr">${i + 1}</span><span>${esc(t("h_" + id + "_titel"))}</span>${SYM.pfeil}</summary>
      <div class="hilfe-inhalt">
        <p>${esc(t("h_" + id + "_text"))}</p>
        <video class="hilfe-video" controls playsinline preload="none" data-poster="hilfe/videos/${sprache}/${id}.jpg" data-src="hilfe/videos/${sprache}/${id}.mp4"></video>
        ${ohneTon ? `<p class="video-info">${esc(t("video_ohne_ton"))}</p>` : ""}
      </div>
    </details>`).join("");
}
$("hilfeThemen").addEventListener("toggle", ev => {
  const d = ev.target; if (!d.matches || !d.matches("details.hilfe-thema")) return;
  const v = d.querySelector("video");
  if (d.open) {
    $("hilfeThemen").querySelectorAll("details[open]").forEach(o => { if (o !== d) o.open = false; });
    if (v && !v.src) {
      v.poster = v.dataset.poster; v.src = v.dataset.src; v.volume = lautstaerke() / 100;
      v.addEventListener("error", () => { const p = document.createElement("p"); p.className = "video-info"; p.textContent = t("video_fehlt"); v.replaceWith(p); }, { once: true });
    }
  } else if (v) { try { v.pause(); } catch (e) {} }
}, true);
$("hilfeThemen").addEventListener("play", ev => { if (ev.target.tagName === "VIDEO") ev.target.volume = lautstaerke() / 100; }, true);
$("lautstaerke").addEventListener("input", () => {
  const v = $("lautstaerke").value; $("lautstaerkeWert").textContent = v; schreiben("ekl_lautstaerke", v);
  $("hilfeThemen").querySelectorAll("video").forEach(x => { x.volume = v / 100; x.muted = v === "0"; });
});
$("btnHilfe").addEventListener("click", () => {
  $("lautstaerke").value = lautstaerke(); $("lautstaerkeWert").textContent = lautstaerke();
  hilfeZeichnen(); fensterAuf("dlgHilfe");
  if (!videoInfo) fetch("hilfe/videos/info.json", { cache: "no-cache" }).then(r => r.ok ? r.json() : null).then(j => { if (j) { videoInfo = j; hilfeZeichnen(); } }).catch(() => {});
});

// ───────────── andere Fenster/Tabs desselben Geräts ─────────────
window.addEventListener("storage", ev => { if (ev.key === "ekl_liste") { listeLaden(); zeichnen(); } });

// ───────────── Start ─────────────
async function start() {
  await katalogLaden(sprache);
  indexBauen(); listeLaden(); texteAnwenden(); sprachListeZeichnen(); themaFarbe();
  $("speicherWarnung").hidden = speicherOk;
  if (breit.matches) tabWechseln("liste"); else zeichnen();
  hashPruefen();
  if ("serviceWorker" in navigator && location.protocol !== "file:") {
    navigator.serviceWorker.register("sw.js", { updateViaCache: "none" }).then(r => { try { r.update(); } catch (e) {} }).catch(() => {});
  }
}
// Schnittstelle für Tests und Hilfe-Videos (keine Daten nach außen)
window.EKL = {
  version: VERSION, get sprache() { return sprache; }, spracheSetzen, tabWechseln, hinzufuegen,
  liste: () => eintraege.map(e => ({ ...e, name: anzeigeName(e) })), artikel: id => ART.get(id), linkErzeugen, textErzeugen,
  iosAnleitung: () => fensterAuf("dlgIos"), fensterZu, zeichnen,
  installTest: () => { installAufforderung = { prompt: async () => {}, userChoice: Promise.resolve({ outcome: "dismissed" }) }; installKarteZeigen(); einstInstallZeichnen(); }
};
start();
})();
