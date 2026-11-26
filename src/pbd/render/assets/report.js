(function () {
  "use strict";
  var d = document, root = d.documentElement, body = d.body;
  root.classList.remove("no-js"); root.classList.add("js");
  var reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  function $(s, el) { return (el || d).querySelector(s); }
  function $$(s, el) { return [].slice.call((el || d).querySelectorAll(s)); }
  function store(k, v) { try { if (v === undefined) return sessionStorage.getItem(k); sessionStorage.setItem(k, v); } catch (e) { return null; } return null; }

  /* ---------------------------------------------------------------- i18n (offline) */
  var CATS = {}; try { CATS = JSON.parse($("#pbd-i18n").textContent); } catch (e) { CATS = {}; }
  var locale = root.getAttribute("data-ui-locale") || "en";
  function raw(key) { var c = CATS[locale] || {}; if (key in c) return c[key]; var f = CATS.en || {}; return key in f ? f[key] : key; }
  function num(n) { try { return new Intl.NumberFormat(locale).format(n); } catch (e) { return String(n); } }
  function t(key, params) {
    var v = raw(key), p = params || {};
    if (v && typeof v === "object") {
      var cat = "other";
      try { cat = new Intl.PluralRules(locale).select(Number(p.n || 0)); } catch (e) { cat = Number(p.n) === 1 ? "one" : "other"; }
      v = (Number(p.n || 0) === 0 && v.zero) ? v.zero : (v[cat] || v.other);
    }
    return String(v).replace(/\{(\w+)\}/g, function (m, k) {
      if (!(k in p)) return m; var x = p[k];
      if (typeof x === "number") return num(x);
      if (x && typeof x === "object" && x.i18n) return t(x.i18n, x.p);
      return String(x);
    });
  }
  function params(el) { try { return JSON.parse(el.getAttribute("data-i18n-p") || "{}"); } catch (e) { return {}; } }
  function applyLocale(next) {
    if (!CATS[next]) return;
    locale = next; root.setAttribute("lang", next); root.setAttribute("data-ui-locale", next);
    $$("[data-i18n]").forEach(function (el) { el.textContent = t(el.getAttribute("data-i18n"), params(el)); });
    $$("[data-i18n-attr]").forEach(function (el) {
      el.getAttribute("data-i18n-attr").split(";").forEach(function (pair) {
        var i = pair.indexOf(":"); if (i < 0) return;
        el.setAttribute(pair.slice(0, i), t(pair.slice(i + 1), params(el)));
      });
    });
    store("pbd-lang", next); updateCount(); renderChips(); updateCrumb();
  }
  var langSel = $("#lang-sel");
  if (langSel) {
    langSel.addEventListener("change", function () { applyLocale(langSel.value); toast(t("lang.content_note", { lang: root.getAttribute("data-content-lang") })); });
    var savedLang = store("pbd-lang"); if (savedLang && savedLang !== locale && CATS[savedLang]) { langSel.value = savedLang; applyLocale(savedLang); }
  }

  /* ---------------------------------------------------------------- theme */
  var themeSel = $("#theme-sel");
  function setTheme(v) { if (v === "system") root.removeAttribute("data-theme"); else root.setAttribute("data-theme", v); store("pbd-theme", v); }
  if (themeSel) {
    var savedTheme = store("pbd-theme"); if (savedTheme) { themeSel.value = savedTheme; setTheme(savedTheme); }
    themeSel.addEventListener("change", function () { setTheme(themeSel.value); });
  }

  /* ---------------------------------------------------------------- appearance (presentation only) */
  var apSel = $("#appearance-sel");
  function setAppearance(v) {
    if (["generic", "azure", "jira"].indexOf(v) < 0) return;
    root.setAttribute("data-appearance", v);
    $$("svg.ti > use").forEach(function (u) { u.setAttribute("href", u.getAttribute("href").replace(/^#t-[a-z]+-/, "#t-" + v + "-")); });
    store("pbd-appearance", v);
  }
  if (apSel) {
    var savedAp = store("pbd-appearance"); if (savedAp && savedAp !== apSel.value) { apSel.value = savedAp; setAppearance(savedAp); }
    apSel.addEventListener("change", function () { setAppearance(apSel.value); });
  }

  /* mirrored controls in the mobile drawer drive the header ones (single source of behaviour) */
  $$("[data-mirror]").forEach(function (m) {
    var main = d.getElementById(m.getAttribute("data-mirror")); if (!main) return;
    m.value = main.value;
    m.addEventListener("change", function () { main.value = m.value; main.dispatchEvent(new Event("change")); });
    main.addEventListener("change", function () { m.value = main.value; });
  });

  /* ---------------------------------------------------------------- toast */
  var toastEl = $("#toast"), toastTimer = 0;
  function toast(msg) {
    if (!toastEl) return; toastEl.textContent = msg; toastEl.classList.add("show");
    clearTimeout(toastTimer); toastTimer = setTimeout(function () { toastEl.classList.remove("show"); }, 2600);
  }

  /* ---------------------------------------------------------------- navigation shell */
  var lastFocus = null;
  function closeNav() { if (body.classList.contains("nav-open")) { body.classList.remove("nav-open"); var m = $("#menu"); if (m) m.setAttribute("aria-expanded", "false"); if (lastFocus) lastFocus.focus(); } }
  var menu = $("#menu");
  if (menu) menu.addEventListener("click", function () {
    lastFocus = menu; body.classList.add("nav-open"); menu.setAttribute("aria-expanded", "true");
    var first = $(".side a"); if (first) first.focus();
  });
  var scrim = $("#scrim"); if (scrim) scrim.addEventListener("click", closeNav);
  var collapse = $("#collapse");
  if (collapse) collapse.addEventListener("click", function () {
    var on = body.classList.toggle("collapsed"); collapse.setAttribute("aria-pressed", on ? "true" : "false");
  });
  d.addEventListener("keydown", function (e) { if (e.key === "Escape") closeNav(); });

  var views = $$(".view");
  function activate(view) {
    views.forEach(function (v) { v.classList.toggle("is-active", v === view); });
    $$(".side a[data-view]").forEach(function (a) {
      if (a.getAttribute("data-view") === view.id) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
    });
    updateCrumb();
  }
  function updateCrumb() {
    var cur = $(".side a[aria-current]"), crumb = $("#crumb-view");
    if (cur && crumb) { var lbl = $(".label", cur); crumb.textContent = lbl ? lbl.textContent : cur.textContent; }
  }
  function focusEl(el) {
    if (!el.hasAttribute("tabindex")) el.setAttribute("tabindex", "-1");
    el.focus({ preventScroll: true });
    el.scrollIntoView({ block: "start", behavior: reduce ? "auto" : "smooth" });
  }
  function route() {
    var id = decodeURIComponent((location.hash || "").slice(1));
    var target = id ? d.getElementById(id) : null;
    if (!target) { if (views[0]) activate(views[0]); return; }
    var view = target.classList.contains("view") ? target : target.closest(".view");
    if (!view) return;
    activate(view); closeNav();
    var art = target.closest("article.item");
    if (art) {
      selectItem(art.getAttribute("data-id"), false);
      if (target !== art) { target.classList.add("flash"); setTimeout(function () { target.classList.remove("flash"); }, 1600); focusEl(target); }
      else focusEl(art);
      return;
    }
    if (target === view) { window.scrollTo(0, 0); var h = $("h2", view); if (h) { h.setAttribute("tabindex", "-1"); h.focus({ preventScroll: true }); } }
    else { if (target.tagName === "DETAILS") target.open = true; focusEl(target); }
  }
  window.addEventListener("hashchange", route);

  /* ---------------------------------------------------------------- explorer */
  var ex = $("#explorer");
  var detail = $("#detail");
  var rows = $$("#tree li[data-id]"), trows = $$("#itable tbody tr[data-id]");
  function norm(s) { return (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase(); }
  rows.forEach(function (li) { li._t = norm(li.getAttribute("data-text")); li._row = $(".row", li); li._kids = $$(":scope > ul > li", li); });
  var byId = {}; rows.forEach(function (li) { byId[li.getAttribute("data-id")] = li; });
  trows.forEach(function (tr) { tr._t = norm(tr.getAttribute("data-text")); });
  var q = $("#q"), fsel = $$("[data-xfilter]");
  var total = rows.length, shown = total;
  function filters() { var f = {}; fsel.forEach(function (s) { if (s.value) f[s.getAttribute("data-xfilter")] = s.value; }); return f; }
  function matches(el, term, f) {
    if (term && el._t.indexOf(term) < 0) return false;
    for (var k in f) { if (el.getAttribute("data-" + k) !== f[k]) return false; }
    return true;
  }
  function highlight(span, term) {
    if (!span) return;
    if (span._o === undefined) span._o = span.textContent;
    var text = span._o; span.textContent = "";
    if (!term) { span.textContent = text; return; }
    var n = norm(text), i = 0, at;
    while ((at = n.indexOf(term, i)) >= 0) {
      span.appendChild(d.createTextNode(text.slice(i, at)));
      var m = d.createElement("mark"); m.textContent = text.slice(at, at + term.length); span.appendChild(m);
      i = at + term.length;
    }
    span.appendChild(d.createTextNode(text.slice(i)));
  }
  function apply() {
    if (!ex) return;
    var term = norm(q ? q.value.trim() : ""), f = filters(), active = !!term || Object.keys(f).length > 0;
    shown = 0;
    function walk(li) {
      var self = matches(li, term, f), any = false;
      li._kids.forEach(function (k) { if (walk(k)) any = true; });
      var keep = self || any;
      li.hidden = !keep; li._row.classList.toggle("ctx", keep && !self && active);
      if (self) shown++;
      if (active && any) { li.classList.remove("collapsed"); var tw = $(".tw", li._row); if (tw) tw.setAttribute("aria-expanded", "true"); }
      highlight($(".t", li._row), self ? term : "");
      return keep;
    }
    rows.filter(function (li) { return !li.parentElement.closest("li[data-id]"); }).forEach(walk);
    trows.forEach(function (tr) { tr.hidden = !matches(tr, term, f); });
    var none = $("#ex-none"); if (none) none.hidden = shown > 0;
    updateCount(); renderChips();
  }
  function updateCount() {
    var c = $("#ex-count"); if (!c) return;
    c.setAttribute("data-i18n-p", JSON.stringify({ n: shown, total: total }));
    c.textContent = t("ex.count", { n: shown }) + " " + t("ex.count_of", { total: total });
  }
  function renderChips() {
    var box = $("#chips"); if (!box) return;
    box.textContent = "";
    fsel.forEach(function (s) {
      if (!s.value) return;
      var label = s.options[s.selectedIndex].textContent, b = d.createElement("button");
      b.type = "button"; b.className = "chip";
      b.setAttribute("aria-label", t("a11y.remove_filter", { label: label }));
      b.appendChild(d.createTextNode(label));
      var x = d.createElementNS("http://www.w3.org/2000/svg", "svg"); x.setAttribute("class", "i sm"); x.setAttribute("aria-hidden", "true");
      var u = d.createElementNS("http://www.w3.org/2000/svg", "use"); u.setAttribute("href", "#i-x"); x.appendChild(u); b.appendChild(x);
      b.addEventListener("click", function () { s.value = ""; apply(); s.focus(); });
      box.appendChild(b);
    });
  }
  if (q) q.addEventListener("input", apply);
  fsel.forEach(function (s) { s.addEventListener("change", apply); });
  var clear = $("#ex-clear");
  if (clear) clear.addEventListener("click", function () { if (q) q.value = ""; fsel.forEach(function (s) { s.value = ""; }); apply(); if (q) q.focus(); });
  function setOpen(li, open) { li.classList.toggle("collapsed", !open); var tw = $(".tw", li._row); if (tw && !tw.classList.contains("leaf")) tw.setAttribute("aria-expanded", open ? "true" : "false"); }
  $$("#tree .tw").forEach(function (tw) {
    tw.addEventListener("click", function () { var li = tw.closest("li[data-id]"); setOpen(li, li.classList.contains("collapsed")); });
  });
  var expandAll = $("#ex-expand"), collapseAll = $("#ex-collapse"), level = $("#ex-level");
  if (expandAll) expandAll.addEventListener("click", function () { rows.forEach(function (li) { setOpen(li, true); }); });
  if (collapseAll) collapseAll.addEventListener("click", function () { rows.forEach(function (li) { setOpen(li, false); }); });
  if (level) level.addEventListener("change", function () {
    var lv = Number(level.value || 99);
    rows.forEach(function (li) { setOpen(li, Number(li.getAttribute("data-depth")) < lv - 1); });
  });
  $$(".seg [data-xview]").forEach(function (b) {
    b.addEventListener("click", function () {
      var v = b.getAttribute("data-xview");
      $$(".seg [data-xview]").forEach(function (o) { o.setAttribute("aria-pressed", o === b ? "true" : "false"); });
      $("#tree-wrap").hidden = v !== "tree"; $("#table-wrap").hidden = v !== "table";
      ex.classList.toggle("wide", v === "table"); store("pbd-xview", v);
    });
  });
  /* table: sort by column (stable, from data-v), reset to backlog order, column visibility */
  var itable = $("#itable");
  /* cells carry no column id: the header row defines the column order (smaller report) */
  function colIndex(col) { var ths = $$("thead th", itable); for (var i = 0; i < ths.length; i++) { if (ths[i].getAttribute("data-col") === col) return i; } return -1; }
  function sortBy(col, dir, numeric) {
    var tb = $("tbody", itable), list = $$("tr", tb);
    list.sort(function (a, b) {
      if (!col) return Number(a.getAttribute("data-pos")) - Number(b.getAttribute("data-pos"));
      var ca = a.cells[colIndex(col)], cb = b.cells[colIndex(col)];
      var va = ca ? ca.getAttribute("data-v") : "", vb = cb ? cb.getAttribute("data-v") : "";
      var empty = (va === "") - (vb === ""); if (empty) return empty; /* unknown always last */
      var r = numeric ? Number(va) - Number(vb) : va.localeCompare(vb, locale, { numeric: true, sensitivity: "base" });
      if (r === 0) r = Number(a.getAttribute("data-pos")) - Number(b.getAttribute("data-pos"));
      return dir === "descending" ? -r : r;
    });
    list.forEach(function (tr) { tb.appendChild(tr); });
    $$("th[data-col]", itable).forEach(function (th) { th.setAttribute("aria-sort", th.getAttribute("data-col") === col ? dir : "none"); });
  }
  if (itable) {
    $$("button.sort", itable).forEach(function (b) {
      b.addEventListener("click", function () {
        var th = b.closest("th"), cur = th.getAttribute("aria-sort");
        sortBy(b.getAttribute("data-sort"), cur === "ascending" ? "descending" : "ascending", b.hasAttribute("data-num"));
      });
    });
    var reset = $("#sort-reset"); if (reset) reset.addEventListener("click", function () { sortBy(null, "none", false); });
    $$("[data-colvis]").forEach(function (cb) {
      cb.addEventListener("change", function () {
        var col = cb.getAttribute("data-colvis");
        var i = colIndex(col);
        $$("tr", itable).forEach(function (row) { if (row.cells[i]) row.cells[i].classList.toggle("hide-col", !cb.checked); });
      });
    });
  }
  var savedView = store("pbd-xview"); if (savedView === "table") { var tb = $(".seg [data-xview='table']"); if (tb) tb.click(); }
  function selectItem(id, push) {
    if (!detail || !id) return;
    $$("article.item", detail).forEach(function (a) { a.classList.toggle("is-active", a.getAttribute("data-id") === id); });
    detail.classList.add("has-selection");
    rows.forEach(function (li) { li._row.classList.toggle("is-selected", li.getAttribute("data-id") === id); });
    $$("tr[data-id]", ex).forEach(function (tr) { tr.classList.toggle("is-selected", tr.getAttribute("data-id") === id); });
    var li = byId[id]; var p = li && li.parentElement.closest("li[data-id]");
    while (p) { setOpen(p, true); p.hidden = false; p = p.parentElement.closest("li[data-id]"); }
    if (ex) ex.classList.add("show-detail");
    if (push) { if (location.hash !== "#item-" + id) history.pushState(null, "", "#item-" + id); route(); }
  }
  if (ex) ex.addEventListener("click", function (e) {
    var a = e.target.closest("a[data-select]"); if (!a) return;
    e.preventDefault(); selectItem(a.getAttribute("data-select"), true);
  });
  $$(".back").forEach(function (b) {
    b.addEventListener("click", function () {
      ex.classList.remove("show-detail"); history.pushState(null, "", "#backlog");
      var sel = $(".row.is-selected a.lbl"); if (sel) sel.focus();
    });
  });
  var tree = $("#tree");
  if (tree) tree.addEventListener("keydown", function (e) {
    var a = e.target.closest("a.lbl"); if (!a) return;
    var vis = $$("#tree a.lbl").filter(function (x) { return x.offsetParent !== null; }), i = vis.indexOf(a), li = a.closest("li[data-id]");
    if (e.key === "ArrowDown" && i < vis.length - 1) { vis[i + 1].focus(); e.preventDefault(); }
    else if (e.key === "ArrowUp" && i > 0) { vis[i - 1].focus(); e.preventDefault(); }
    else if (e.key === "ArrowRight" && li._kids.length) { setOpen(li, true); e.preventDefault(); }
    else if (e.key === "ArrowLeft") {
      if (li._kids.length && !li.classList.contains("collapsed")) setOpen(li, false);
      else { var par = li.parentElement.closest("li[data-id]"); if (par) $("a.lbl", par).focus(); }
      e.preventDefault();
    }
  });

  /* ---------------------------------------------------------------- generic table/card filters */
  $$("[data-filter-for]").forEach(function (sel) {
    sel.addEventListener("change", function () {
      var box = d.getElementById(sel.getAttribute("data-filter-for")), attr = "data-" + sel.getAttribute("data-attr");
      var group = $$("[data-filter-for='" + sel.getAttribute("data-filter-for") + "']");
      var n = 0;
      $$("[data-row]", box).forEach(function (r) {
        var ok = group.every(function (g) { return !g.value || r.getAttribute("data-" + g.getAttribute("data-attr")) === g.value; });
        r.hidden = !ok; if (ok) n++;
      });
      var out = d.getElementById(sel.getAttribute("data-filter-for") + "-n"); if (out) out.textContent = num(n);
      void attr;
    });
  });
  d.addEventListener("click", function (e) {
    var g = e.target.closest("[data-goto]"); if (!g) return;
    var parts = g.getAttribute("data-goto").split("|"), sel = d.getElementById(parts[1]);
    if (sel) { sel.value = parts[2] || ""; sel.dispatchEvent(new Event("change")); }
    location.hash = parts[0];
  });

  /* ---------------------------------------------------------------- copy, download, print */
  function fallbackCopy(text) {
    var ta = d.createElement("textarea"); ta.value = text; ta.setAttribute("readonly", ""); ta.className = "sr-only";
    body.appendChild(ta); ta.select(); var ok = false; try { ok = d.execCommand("copy"); } catch (e) { ok = false; }
    if (!ok) { toast(t("toast.copy_failed")); return false; }
    body.removeChild(ta); return true;
  }
  d.addEventListener("click", function (e) {
    var b = e.target.closest("[data-copy]"); if (!b) return;
    var text = b.getAttribute("data-copy");
    if (b.getAttribute("data-copy-link") !== null) text = location.href.split("#")[0] + "#" + text;
    function done() { b.classList.add("done"); toast(t("toast.copied")); setTimeout(function () { b.classList.remove("done"); }, 1200); }
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, function () { if (fallbackCopy(text)) done(); });
    else if (fallbackCopy(text)) done();
  });
  d.addEventListener("click", function (e) {
    var b = e.target.closest("[data-download]"); if (!b) return;
    var src = d.getElementById(b.getAttribute("data-download")), name = b.getAttribute("data-filename") || "data.json";
    var url = URL.createObjectURL(new Blob([src.textContent], { type: "application/json" }));
    var a = d.createElement("a"); a.href = url; a.download = name; body.appendChild(a); a.click(); body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000); toast(t("toast.downloaded", { name: name }));
  });
  var pr = $("#print"); if (pr) pr.addEventListener("click", function () { window.print(); });
  var pt = $("#print-tech"); if (pt) pt.addEventListener("change", function () { body.classList.toggle("print-tech", pt.checked); });

  apply();
  route();
})();
