/* Shared helpers for both statistic pages. window.STAT is inlined by build_statistic.py. */
const S = window.STAT || {};

const n = (v) => (v === null || v === undefined) ? "—" : v.toLocaleString();
const pct = (a, b) => (b ? (100 * a / b) : 0);

function el(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined) continue;
    if (k === "class") e.className = v;
    else if (k === "style") e.style.cssText = v;
    else e.setAttribute(k, v);
  }
  for (const kid of kids.flat()) {
    if (kid === null || kid === undefined || kid === false) continue;
    e.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return e;
}

/* A panel says where its numbers came from, always. `state:"off"` greys it out and the caption
   carries the reason — a panel with no data explains itself rather than disappearing, which is
   how a missing recorder gets noticed at all. */
function panel(title, why, source, body, opts) {
  const o = opts || {};
  const s = el("section", { class: (o.wide ? "wide" : "") + (o.off ? " off" : "") },
    el("h2", {}, title),
    el("p", { class: "why" }, why));
  for (const part of [].concat(body)) if (part) s.append(part);
  if (source) s.append(el("p", { class: "src" }, source));
  return s;
}

function table(headers, rows) {
  const t = el("table", {},
    el("thead", {}, el("tr", {}, headers.map((h, i) =>
      el("th", { class: (typeof h === "object" && h.n) ? "n" : "" },
        typeof h === "object" ? h.t : h)))),
    el("tbody", {}, rows.map((r) => el("tr", {}, r.map((c) =>
      (c && c.nodeType) ? el("td", {}, c)
        : (typeof c === "object" && c !== null)
          ? el("td", { class: c.n ? "n" : "" }, c.t)
          : el("td", {}, c === null || c === undefined ? "—" : String(c)))))));
  return t;
}

function bar(share, cls) {
  return el("div", { class: "bar " + (cls || ""), style: `width:${Math.max(share, 0.5)}%` });
}

/* Newest first, like Sum-Usage-Claude — the owner reads the top of the page, not the bottom. */
function newestFirst(rows, key) {
  return rows.slice().sort((a, b) => String(b[key]).localeCompare(String(a[key])));
}

function head(page) {
  const h = document.querySelector("header");
  h.append(
    el("h1", {}, `${S.repo || "repository"} · statistics`),
    el("p", { class: "sub" }, `built ${S.built || "—"} · every number names the file it came from`),
    el("nav", {},
      el("a", { href: "index.html", class: page === 1 ? "on" : "" }, "1 · overview"),
      el("a", { href: "detail.html", class: page === 2 ? "on" : "" }, "2 · what fires, what breaks")));
}
