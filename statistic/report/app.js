/* Shared chrome and charts for the three statistic pages.
   window.STAT is inlined by build_statistic.py — no fetch, no network, no dependency.

   🎯 [owner, 2026-09-23] English is the primary language and Thai is the second line, smaller.
   Graphics carry the numbers; tables are for the rows a reader actually scans.
   🔴 Nothing here names a model, a vendor or a currency: this plugin does not know which LLM
   anybody runs, whether it is local, or what any of it is charged at. */
const S = window.STAT || {};
const PAL = ["#6f9bff", "#e0813d", "#4fbf7f", "#b98cf0", "#4bb8c9", "#e0655f", "#9aa4b8"];

const n = (v) => (v === null || v === undefined) ? "—" : Math.round(v).toLocaleString();
const pct = (a, b) => (b ? (100 * a / b) : 0);
const short = (v) => v >= 1e9 ? (v / 1e9).toFixed(1) + "B"
  : v >= 1e6 ? (v / 1e6).toFixed(1) + "M"
    : v >= 1e3 ? (v / 1e3).toFixed(1) + "k" : String(Math.round(v || 0));

/* ---------------------------------------------------------------- language and theme

   🎯 [owner, 2026-09-23] Two toggles in the top right, the way Sum-Usage-Claude has them.
   English is the default; Thai replaces it rather than sitting under it, because a page that
   prints every line twice is the "too much text" the first build was told off for.

   Both are remembered in localStorage and applied before the first paint, so the page does not
   flash the other theme on every load. A read that throws — a private window, blocked storage —
   falls back to the default rather than taking the page down with it. */
function pref(key, fallback) {
  try { return localStorage.getItem("stat." + key) || fallback; } catch (e) { return fallback; }
}
function setPref(key, value) {
  try { localStorage.setItem("stat." + key, value); } catch (e) { /* not worth a failure */ }
}
const LANG = pref("lang", "en") === "th" ? "th" : "en";
/* `T(en, th)` is every string on these pages. A missing Thai falls back to the English rather
   than to an empty panel. */
const T = (en, th) => (LANG === "th" && th) ? th : en;

/* 🎯 [owner, 2026-09-23] Dark is the default, and English is the default. Not "follow the system"
   — a page whose look depends on a setting the reader did not make here is a page that looks
   different every time somebody opens it on a different machine. */
function applyTheme() {
  document.documentElement.setAttribute("data-theme", pref("theme", "dark"));
}
applyTheme();

function toggles() {
  const lang = el("button", { class: "tog", type: "button" }, "ไทย / EN");
  lang.addEventListener("click", () => { setPref("lang", LANG === "th" ? "en" : "th"); location.reload(); });
  const theme = el("button", { class: "tog", type: "button" }, "Light / dark");
  theme.addEventListener("click", () => {
    const now = document.documentElement.getAttribute("data-theme");
    const next = now === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    setPref("theme", next);
  });
  return el("div", { class: "togs" }, lang, theme);
}


function el(tag, attrs, ...kids) {
  const ns = ["svg", "g", "path", "circle", "rect", "text", "line", "polyline", "title"];
  const e = ns.includes(tag)
    ? document.createElementNS("http://www.w3.org/2000/svg", tag)
    : document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined) continue;
    if (k === "class") e.setAttribute("class", v);
    else e.setAttribute(k, String(v));
  }
  for (const kid of kids.flat()) {
    if (kid === null || kid === undefined || kid === false) continue;
    e.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return e;
}

/* A panel always says where its numbers came from. `off` greys it and the caption carries the
   reason — a panel with no data explains itself rather than disappearing, which is how a missing
   recorder gets noticed at all. */
function panel(en, th, source, body, opts) {
  const o = opts || {};
  const s = el("section", { class: (o.wide ? "wide " : "") + (o.off ? "off" : "") },
    el("h2", {}, T(en, th)));
  for (const part of [].concat(body)) if (part) s.append(part);
  if (source) s.append(el("p", { class: "src" }, source));
  return s;
}

function table(headers, rows) {
  return el("table", {},
    el("thead", {}, el("tr", {}, headers.map((h) =>
      el("th", { class: (typeof h === "object" && h.n) ? "n" : "" },
        typeof h === "object" ? h.t : h)))),
    el("tbody", {}, rows.map((r) => el("tr", {}, r.map((c) =>
      (c && c.nodeType) ? el("td", {}, c)
        : (c && typeof c === "object")
          ? el("td", { class: c.n ? "n" : "" }, c.t)
          : el("td", {}, c === null || c === undefined ? "—" : String(c)))))));
}

/* ---------------------------------------------------------------- charts, all inline SVG */

function donut(parts, opts) {
  const o = opts || {}, size = o.size || 132, r = size / 2 - 11, C = 2 * Math.PI * r;
  const total = parts.reduce((a, p) => a + p.value, 0) || 1;
  let at = 0;
  const ring = parts.map((p, i) => {
    const frac = p.value / total, dash = `${(frac * C).toFixed(2)} ${C.toFixed(2)}`;
    const c = el("circle", {
      cx: size / 2, cy: size / 2, r, fill: "none", "stroke-width": 15,
      stroke: p.colour || PAL[i % PAL.length], "stroke-dasharray": dash,
      "stroke-dashoffset": (-at * C).toFixed(2),
      transform: `rotate(-90 ${size / 2} ${size / 2})`,
    }, el("title", {}, `${p.label} · ${n(p.value)} (${(frac * 100).toFixed(1)}%)`));
    at += frac;
    return c;
  });
  const svg = el("svg", { viewBox: `0 0 ${size} ${size}`, width: size, height: size,
    class: "chart" }, ring,
    el("text", { x: size / 2, y: size / 2 - 1, "text-anchor": "middle", class: "ctr" },
      o.centre || short(total)),
    o.sub ? el("text", { x: size / 2, y: size / 2 + 15, "text-anchor": "middle", class: "ctrsub" },
      o.sub) : null);
  return el("div", { class: "donutwrap" }, svg, legend(parts));
}

function legend(parts) {
  const total = parts.reduce((a, p) => a + p.value, 0) || 1;
  return el("ul", { class: "legend" }, parts.map((p, i) =>
    el("li", {},
      el("i", { style: `background:${p.colour || PAL[i % PAL.length]}` }),
      el("span", { class: "lab" }, p.label),
      el("span", { class: "val" }, `${(100 * p.value / total).toFixed(1)}%`))));
}

/* A sparkline that is readable at 40px tall: an area under a line, with the last point marked. */
function spark(values, opts) {
  const o = opts || {}, w = o.width || 320, h = o.height || 46, pad = 3;
  const max = Math.max(1, ...values), step = values.length > 1 ? (w - 2 * pad) / (values.length - 1) : 0;
  const pt = (v, i) => [pad + i * step, h - pad - (h - 2 * pad) * (v / max)];
  const line = values.map(pt).map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = `${pad},${h - pad} ${line} ${(pad + (values.length - 1) * step).toFixed(1)},${h - pad}`;
  const [lx, ly] = pt(values[values.length - 1] ?? 0, values.length - 1);
  return el("svg", { viewBox: `0 0 ${w} ${h}`, class: "chart spark",
    preserveAspectRatio: "none" },
    el("polyline", { points: area, fill: o.colour || PAL[0], "fill-opacity": .16, stroke: "none" }),
    el("polyline", { points: line, fill: "none", stroke: o.colour || PAL[0], "stroke-width": 1.8,
      "stroke-linejoin": "round", "stroke-linecap": "round" }),
    el("circle", { cx: lx, cy: ly, r: 2.6, fill: o.colour || PAL[0] }));
}

/* Bars with the label inside the row, so a long feature name never squeezes the bar. */
function hbars(rows, opts) {
  const o = opts || {}, max = Math.max(1, ...rows.map((r) => r.value));
  return el("ul", { class: "hbars" }, rows.map((r) =>
    el("li", { class: r.dim ? "dim" : "" },
      el("span", { class: "hlab" }, T(r.label, r.th)),
      el("span", { class: "htrack" },
        el("span", { class: "hfill", style: `width:${Math.max(pct(r.value, max), 1.5)}%;`
          + `background:${r.colour || (r.dim ? "var(--grey)" : PAL[0])}` })),
      el("span", { class: "hval" }, r.text ?? n(r.value)))));
}

/* Hour-of-day, drawn as a heat strip rather than 24 tiny bars — it reads at a glance and it does
   not lie about a quiet hour by giving it a visible stub. */
function heat(values, labels) {
  const max = Math.max(1, ...values);
  return el("div", { class: "heatwrap" },
    el("div", { class: "heat" }, values.map((v, i) =>
      el("span", { style: `opacity:${(0.10 + 0.9 * (v / max)).toFixed(3)}`,
        title: `${String(i).padStart(2, "0")}:00 · ${n(v)}` }))),
    el("div", { class: "hlabel" }, (labels || ["00", "06", "12", "18", "23"]).map((l) =>
      el("span", {}, l))));
}

function stackbar(parts) {
  const total = parts.reduce((a, p) => a + p.value, 0) || 1;
  return el("div", { class: "stack" }, parts.map((p, i) =>
    el("span", { style: `width:${Math.max(100 * p.value / total, 0.4)}%;`
      + `background:${p.colour || PAL[i % PAL.length]}`,
      title: `${p.label} · ${n(p.value)}` })));
}

/* A real bar chart: gridlines, a value axis, the tallest bar lifted, and a label over it — the
   shape a reader can scan without a tooltip. Clicking a bar drills into that day. */
function bars(rows, opts) {
  const o = opts || {}, W = 760, H = 210, L = 44, B = 26, T0 = 20;
  const max = Math.max(1, ...rows.map((r) => r.value));
  const step = (W - L) / Math.max(rows.length, 1);
  const bw = Math.max(4, Math.min(38, step * 0.62));
  const y = (v) => T0 + (H - T0 - B) * (1 - v / max);
  const ticks = [0, 0.5, 1].map((f) => f * max);
  const kids = [];
  for (const t of ticks) {
    kids.push(el("line", { x1: L, x2: W, y1: y(t), y2: y(t), class: "grid" }));
    kids.push(el("text", { x: L - 8, y: y(t) + 4, "text-anchor": "end", class: "axis" }, short(t)));
  }
  rows.forEach((r, i) => {
    const cx = L + step * i + (step - bw) / 2, top = y(r.value);
    const g = el("g", { class: "barg" + (r.value === max ? " peak" : "") },
      el("rect", { x: cx, y: top, width: bw, height: Math.max(H - B - top, 1), rx: 3 },
        el("title", {}, `${r.label} · ${n(r.value)}`)));
    if (r.value === max) {
      g.append(el("text", { x: cx + bw / 2, y: top - 6, "text-anchor": "middle", class: "peaklab" },
        short(r.value)));
    }
    if (o.onPick) {
      g.setAttribute("class", g.getAttribute("class") + " pick");
      g.addEventListener("click", () => o.onPick(r));
    }
    kids.push(g);
    if (rows.length <= 14 || i % Math.ceil(rows.length / 10) === 0) {
      kids.push(el("text", { x: cx + bw / 2, y: H - 8, "text-anchor": "middle", class: "axis" },
        r.tick ?? r.label));
    }
  });
  return el("svg", { viewBox: `0 0 ${W} ${H}`, class: "chart bars" }, kids);
}

/* One row per day, one cell per hour — the calendar that reads at a glance. Colour is the part of
   the day, opacity is the weight, so a quiet hour is visibly quiet instead of being given a stub. */
function calendar(rowsIn) {
  const max = Math.max(1, ...rowsIn.flatMap((r) => r.cells));
  const band = (h) => h < 8 ? PAL[3] : h < 17 ? PAL[2] : PAL[1];
  const grid = el("div", { class: "cal" }, rowsIn.slice().reverse().map((r) =>
    el("div", { class: "calrow" },
      el("span", { class: "calday" }, r.day.slice(5)),
      el("div", { class: "calcells" }, r.cells.map((v, h) =>
        el("span", {
          style: `background:${band(h)};opacity:${(0.07 + 0.93 * (v / max)).toFixed(3)}`,
          title: `${r.day} ${String(h).padStart(2, "0")}:00 · ${n(v)}`,
        }))))));
  const key = el("div", { class: "calkey" },
    [[PAL[3], T("night 00–08", "กลางคืน 00–08")],
     [PAL[2], T("work hours 08–17", "เวลางาน 08–17")],
     [PAL[1], T("evening 17–24", "เย็น 17–24")]].map(([c, lab]) =>
      el("span", {}, el("i", { style: `background:${c}` }), lab)),
    el("span", { class: "calnote" },
      T("darker is heavier · left to right 00:00 → 23:00",
        "เข้มกว่าคือหนักกว่า · ซ้ายไปขวา 00:00 → 23:00")));
  return el("div", {}, grid, key);
}

/* The opening panel: one number, the sentence that explains it, and two bars to the same scale. */
function hero(big, sentence, bars2) {
  const total = Math.max(...bars2.map((b) => b.value), 1);
  return el("section", { class: "wide heroP" },
    el("div", { class: "heroL" },
      el("p", { class: "herobig" }, big.value),
      el("p", { class: "herolab" }, big.label)),
    el("div", { class: "heroR" },
      el("p", { class: "herosent" }, sentence),
      ...bars2.map((b) => el("div", { class: "herobar" },
        el("div", { class: "herobarhead" },
          el("span", {}, b.label), el("b", {}, b.text ?? short(b.value))),
        el("div", { class: "herotrack" },
          el("div", { class: "herofill", style: `width:${Math.max(pct(b.value, total), 0.6)}%;`
            + `background:${b.colour}` }))))));
}


function stat(big, en, th) {
  return el("div", { class: "stat" },
    el("p", { class: "big" }, big),
    el("p", { class: "statlab" }, T(en, th)));
}

/* ---------------------------------------------------------------- period, and the picker */

const SERIES = S.series || { days: [], months: [], fields: [] };

function readPeriod() {
  const q = new URLSearchParams(location.search);
  const grain = q.get("grain") === "day" ? "day" : "month";
  const at = q.get("at") || null;
  return { grain, at };
}

function periodRows(p) {
  return p.grain === "day" ? SERIES.days : SERIES.months;
}

function currentRow(p) {
  const rows = periodRows(p);
  if (!rows.length) return null;
  const key = p.grain === "day" ? "day" : "month";
  return (p.at && rows.find((r) => r[key] === p.at)) || rows[rows.length - 1];
}

/* The picker is a popover anchored under the button, not a dropdown that pushes the page around:
   choosing a month and then drilling into one of its days is two clicks in the same place. */
function picker(p) {
  const key = p.grain === "day" ? "day" : "month";
  const row = currentRow(p);
  const btn = el("button", { class: "period", type: "button" },
    el("span", {}, row ? row[key] : "—"),
    el("em", {}, p.grain === "day" ? T("day", "รายวัน") : T("month", "รายเดือน")));
  const pop = el("div", { class: "pop", hidden: "hidden" });

  const tabs = el("div", { class: "poptabs" },
    ["month", "day"].map((g) => {
      const b = el("button", { type: "button", class: g === p.grain ? "on" : "" },
        g === "month" ? T("month", "เดือน") : T("day", "วัน"));
      b.addEventListener("click", () => go(g, null));
      return b;
    }));
  const list = el("div", { class: "poplist" },
    periodRows(p).slice().reverse().slice(0, 60).map((r) => {
      const b = el("button", { type: "button", class: row && r[key] === row[key] ? "on" : "" },
        el("span", {}, r[key]),
        el("em", {}, `${short(r.commands)} cmd · ${short(r.opens)} opens`));
      b.addEventListener("click", () => go(p.grain, r[key]));
      return b;
    }));
  pop.append(tabs, list,
    el("p", { class: "popfoot" },
      T(`kept for ${SERIES.keep_months || 12} months`, `เก็บย้อนหลัง ${SERIES.keep_months || 12} เดือน`)));

  btn.addEventListener("click", (e) => { e.stopPropagation(); pop.hidden = !pop.hidden; });
  document.addEventListener("click", () => { pop.hidden = true; });
  pop.addEventListener("click", (e) => e.stopPropagation());
  return el("div", { class: "periodwrap" }, btn, pop);
}

function go(grain, at) {
  const q = new URLSearchParams(location.search);
  q.set("grain", grain);
  if (at) q.set("at", at); else q.delete("at");
  location.search = q.toString();
}

const PAGES = [
  { file: "index.html", en: "impact", th: "ความต่าง" },
  { file: "features.html", en: "features", th: "ฟีเจอร์" },
  { file: "usage.html", en: "usage", th: "การใช้งาน" },
];

function head(page, p) {
  const h = document.querySelector("header");
  h.append(
    el("div", { class: "topline" },
      el("div", {},
        el("h1", {}, `${S.repo || "repository"} · ${T("statistics", "สถิติ")}`),
        el("p", { class: "sub" }, `${T("built", "สร้างเมื่อ")} ${S.built || "—"} · `
          + T("every number names the file it came from", "ทุกตัวเลขบอกว่ามาจากไฟล์ไหน"))),
      el("div", { class: "topright" }, p ? picker(p) : null, toggles())),
    el("nav", {}, PAGES.map((x, i) =>
      el("a", { href: x.file + location.search, class: i + 1 === page ? "on" : "" },
        `${i + 1} · ${T(x.en, x.th)}`))));
}
