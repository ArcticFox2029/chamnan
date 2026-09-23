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
    el("h2", {}, en), th ? el("p", { class: "th" }, th) : null);
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
      el("span", { class: "hlab" }, r.label, r.th ? el("em", {}, r.th) : null),
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

function stat(big, en, th) {
  return el("div", { class: "stat" },
    el("p", { class: "big" }, big),
    el("p", { class: "statlab" }, en),
    th ? el("p", { class: "th" }, th) : null);
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
    el("em", {}, p.grain === "day" ? "day · รายวัน" : "month · รายเดือน"));
  const pop = el("div", { class: "pop", hidden: "hidden" });

  const tabs = el("div", { class: "poptabs" },
    ["month", "day"].map((g) => {
      const b = el("button", { type: "button", class: g === p.grain ? "on" : "" },
        g === "month" ? "month · เดือน" : "day · วัน");
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
    el("p", { class: "popfoot" }, `kept for ${SERIES.keep_months || 12} months · เก็บ 12 เดือน`));

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
        el("h1", {}, `${S.repo || "repository"} · statistics`),
        el("p", { class: "sub" }, `built ${S.built || "—"} · every number names the file it came from`),
        el("p", { class: "th" }, "ทุกตัวเลขบอกว่ามาจากไฟล์ไหน")),
      p ? picker(p) : null),
    el("nav", {}, PAGES.map((x, i) =>
      el("a", { href: x.file + location.search, class: i + 1 === page ? "on" : "" },
        `${i + 1} · ${x.en}`, el("em", {}, x.th)))));
}
