(function () {
  var origin = window.__DATALENS_NEURO_ORIGIN;
  if (!origin || document.getElementById("datalens-neuro-root")) return;
  var root = document.createElement("div");
  root.id = "datalens-neuro-root";
  root.innerHTML = [
    "<style>",
    "#datalens-neuro-root{font:14px/1.4 sans-serif;color:#222}",
    "#datalens-neuro-root .dn-toggle{position:fixed;right:16px;bottom:16px;z-index:100000;padding:10px 14px;border:0;border-radius:8px;background:#3252a8;color:#fff;cursor:pointer}",
    "#datalens-neuro-root .dn-panel{position:fixed;top:0;right:0;z-index:100000;width:420px;height:100vh;background:#fff;box-shadow:-8px 0 24px rgba(0,0,0,.15);display:flex;flex-direction:column}",
    "#datalens-neuro-root .dn-panel-closed{display:none}",
    "#datalens-neuro-root .dn-head,#datalens-neuro-root .dn-form{padding:12px;border-bottom:1px solid #e5e5e5;display:flex;gap:8px;align-items:center}",
    "#datalens-neuro-root .dn-formula-on{background:#e8eefc}",
    "#datalens-neuro-root .dn-page{padding:8px 12px;color:#666;font-size:12px;border-bottom:1px solid #e5e5e5}",
    "#datalens-neuro-root .dn-form{border-bottom:0;border-top:1px solid #e5e5e5}",
    "#datalens-neuro-root .dn-log{flex:1;overflow:auto;padding:12px}",
    "#datalens-neuro-root .dn-msg{margin:0 0 12px}",
    "#datalens-neuro-root .dn-user{font-weight:600}",
    "#datalens-neuro-root pre{white-space:pre-wrap;background:#f6f6f6;padding:8px}",
    "#datalens-neuro-root textarea{flex:1;min-height:56px}",
    "</style>",
    "<button class='dn-toggle' type='button'></button>",
    "<aside class='dn-panel dn-panel-closed'>",
    "<div class='dn-head'><strong class='dn-title'></strong><button class='dn-formula' type='button'>Формулы</button><button class='dn-new' type='button'>Новый диалог</button><button class='dn-close' type='button'>Закрыть</button></div>",
    "<div class='dn-page'></div>",
    "<div class='dn-log'></div>",
    "<form class='dn-form'><textarea name='q'></textarea><button type='submit'>Спросить</button></form>",
    "</aside>"
  ].join("");
  var title = __NEURO_UI_TITLE_JSON__;
  root.querySelector(".dn-toggle").textContent = title;
  root.querySelector(".dn-title").textContent = title;
  document.body.appendChild(root);
  var panel = root.querySelector(".dn-panel");
  var log = root.querySelector(".dn-log");
  var form = root.querySelector(".dn-form");
  var field = form.querySelector("textarea");
  var busy = false;
  var expired = "";
  var formulaMode = sessionStorage.getItem("datalens-neuro-formula") === "1";
  var modeToken = 0;

  function esc(text) {
    return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
  function inline(text) {
    text = esc(text);
    text = text.replace(/`([^`]+)`/g, "<code>$1</code>");
    text = text.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/__(.+?)__/g, "<b>$1</b>");
    text = text.replace(/(^|[^*])\*([^*]+)\*/g, "$1<i>$2</i>").replace(/(^|[^_])_([^_]+)_/g, "$1<i>$2</i>");
    return text;
  }
  function htmlOf(markdown, sources, steps) {
    var lines = String(markdown || "").split("\n");
    var out = [];
    var i = 0;
    while (i < lines.length) {
      if (lines[i].trim().charAt(0) === "|" && lines[i].trim().slice(-1) === "|") {
        var rows = [];
        while (i < lines.length && lines[i].indexOf("|") !== -1) {
          if (!/^\s*\|?\s*:?-{3,}/.test(lines[i])) rows.push(lines[i].trim().replace(/^\||\|$/g, "").split("|").map(function (c) { return c.trim(); }));
          i++;
        }
        var width = Math.max.apply(null, rows.map(function (r) { return r.length; }));
        var sized = rows.map(function (r) { while (r.length < width) r.push(""); return r; });
        var widths = [];
        for (var c = 0; c < width; c++) widths.push(Math.max.apply(null, sized.map(function (r) { return r[c].length; })));
        out.push("<pre>" + esc(sized.map(function (r) { return r.map(function (cell, n) { return cell + " ".repeat(widths[n] - cell.length); }).join("  ").trimEnd(); }).join("\n")) + "</pre>");
        continue;
      }
      var line = lines[i++];
      if (line.indexOf("```") === 0) {
        var buf = [];
        while (i < lines.length && lines[i].indexOf("```") !== 0) buf.push(lines[i++]);
        i++;
        out.push("<pre>" + esc(buf.join("\n")) + "</pre>");
      } else if (line.charAt(0) === "#") out.push("<b>" + inline(line.replace(/^#+\s*/, "")) + "</b>");
      else if (/^\s*[-*]\s+/.test(line)) out.push("• " + inline(line.replace(/^\s*[-*]\s+/, "")));
      else out.push(inline(line));
    }
    var names = {dataset: "датасет", chart: "чарт", dashboard: "дашборд"};
    if (sources && sources.length) out.push("Источники: " + sources.map(function (s) { return (names[s.type] || s.type) + " " + s.id; }).join(", "));
    if (steps && steps.length) out.push("<details><summary>Как посчитано</summary>" + steps.map(function (s) { return esc(s.tool + " " + s.status); }).join("<br>") + "</details>");
    return out.join("<br>");
  }
  function bubble(role, content, sources, steps) {
    var node = document.createElement("div");
    node.className = "dn-msg" + (role === "user" ? " dn-user" : "");
    node.innerHTML = role === "user" ? esc(content) : htmlOf(content, sources, steps);
    log.appendChild(node);
    log.scrollTop = log.scrollHeight;
    return node;
  }
  function paint(messages) {
    log.innerHTML = "";
    (messages || []).forEach(function (m) { bubble(m.role, m.content, m.sources, m.steps); });
  }
  function failText(status, requestId) {
    if (status === 401) return "Обновите страницу DataLens";
    if (status === 403) return "Недостаточно прав";
    if (status === 429) return "Слишком много запросов, подождите минуту.";
    if (status === 409) return "Предыдущий вопрос ещё обрабатывается.";
    if (status === 503) return "Нейроаналитик выключен администратором.";
    return "Не удалось получить ответ. Код: " + (requestId || "");
  }
  function call(method, path, payload) {
    return fetch(origin + path, {
      method: method,
      credentials: "include",
      headers: {"content-type": "application/json"},
      body: payload ? JSON.stringify(payload) : undefined
    }).then(function (response) {
      return response.json().catch(function () { return {}; }).then(function (body) {
        return {ok: response.ok, status: response.status, body: body, requestId: response.headers.get("x-request-id")};
      });
    }).catch(function () { return {ok: false, status: 0, body: {}, requestId: ""}; });
  }
  function entryFromSegment(segment) {
    if (/^[0-9a-z]{13}$/.test(segment)) return segment;
    if (/^[0-9a-z]{13}-/.test(segment)) return segment.slice(0, 13);
    return "";
  }
  function pageContext() {
    var parts = location.pathname.split("/").filter(Boolean);
    var ctx = {};
    if (parts.length === 1) {
      var dash = entryFromSegment(parts[0]);
      if (dash) ctx.dashboardId = dash;
    } else if (parts.length === 2 && (parts[0] === "wizard" || parts[0] === "ql")) {
      var chart = entryFromSegment(parts[1]);
      if (chart) ctx.chartId = chart;
    }
    if (ctx.dashboardId) {
      var tab = new URLSearchParams(location.search).get("tab");
      if (tab && tab.length <= 64 && !/[\s]/.test(tab)) ctx.tabId = tab;
    }
    paintPage(ctx, null);
    return ctx;
  }
  function formulaContext() {
    var parts = location.pathname.split("/").filter(Boolean);
    if (!(parts.length === 2 && (parts[0] === "wizard" || parts[0] === "ql"))) return null;
    var chartId = entryFromSegment(parts[1]);
    if (!chartId) return null;
    return {chartId: chartId, chartKind: parts[0]};
  }
  function applyMode() {
    if (formulaMode) sessionStorage.setItem("datalens-neuro-formula", "1");
    else sessionStorage.removeItem("datalens-neuro-formula");
    if (formulaMode) root.querySelector(".dn-formula").classList.add("dn-formula-on");
    else root.querySelector(".dn-formula").classList.remove("dn-formula-on");
    if (!expired) field.placeholder = formulaMode ? "Опишите формулу или вставьте её" : "";
    pageContext();
    var token = ++modeToken;
    var path = formulaMode ? "/v1/ui/formula/thread" : "/v1/ui/thread";
    paint([]);
    return call("GET", path).then(function (thread) {
      if (token !== modeToken || !thread.ok) return;
      paint(thread.body.messages || []);
    });
  }
  function paintPage(ctx, filterNames) {
    var label = root.querySelector(".dn-page");
    if (formulaMode) {
      var formulaLine = "Формулы";
      if (ctx.chartId) formulaLine += " · Чарт " + ctx.chartId;
      label.textContent = formulaLine;
      return;
    }
    var line = "";
    if (ctx.dashboardId && ctx.tabId) line = "Дашборд " + ctx.dashboardId + ", вкладка " + ctx.tabId;
    else if (ctx.dashboardId) line = "Дашборд " + ctx.dashboardId + ", первая вкладка";
    else if (ctx.chartId) line = "Чарт " + ctx.chartId;
    else line = "На этой странице дашборд не открыт";
    if (ctx.dashboardId) {
      if (filterNames && filterNames.length) line += ", фильтры: " + filterNames.join(", ");
      else line += ", фильтры по умолчанию";
    }
    label.textContent = line;
  }
  var cachedCsrf = "";
  function remember(params, name, value) {
    if (!name || name === "__meta__") return;
    if (value === "" || value == null) return;
    if (Array.isArray(value)) {
      if (!value.length) return;
      params[name] = value;
      return;
    }
    if (typeof value === "object") return;
    params[name] = value;
  }
  function filtersFromState(payload) {
    var data = payload && payload.data;
    var params = {};
    if (!data || typeof data !== "object" || Array.isArray(data)) return params;
    Object.keys(data).forEach(function (widgetId) {
      if (widgetId === "__meta__") return;
      var controls = data[widgetId] && data[widgetId].params;
      if (!controls || typeof controls !== "object" || Array.isArray(controls)) return;
      Object.keys(controls).forEach(function (controlId) {
        var fields = controls[controlId];
        if (!fields || typeof fields !== "object" || Array.isArray(fields)) {
          remember(params, controlId, fields);
          return;
        }
        Object.keys(fields).forEach(function (name) {
          remember(params, name, fields[name]);
        });
      });
    });
    var names = Object.keys(params);
    while (names.length && JSON.stringify(params).length > 1800) {
      delete params[names.pop()];
    }
    return params;
  }
  function pageStore() {
    var nodes = [document.getElementById("root"), document.getElementById("app"), document.body];
    var kids = document.body ? document.body.children : [];
    for (var k = 0; k < kids.length && k < 8; k++) nodes.push(kids[k]);
    for (var n = 0; n < nodes.length; n++) {
      var el = nodes[n];
      if (!el) continue;
      var keys = Object.keys(el);
      for (var i = 0; i < keys.length; i++) {
        if (keys[i].indexOf("__reactContainer") !== 0 && keys[i].indexOf("__reactFiber") !== 0) continue;
        var root = el[keys[i]];
        var fiber = root && root.current ? root.current : root;
        var queue = [fiber];
        var head = 0;
        while (head < queue.length && head < 5000) {
          var node = queue[head++];
          if (!node) continue;
          var props = node.memoizedProps;
          if (props && props.store && typeof props.store.getState === "function") return props.store.getState();
          if (node.child) queue.push(node.child);
          if (node.sibling) queue.push(node.sibling);
        }
      }
    }
    return null;
  }
  function liveStateData() {
    try {
      var state = pageStore();
      var dash = state && state.dash;
      if (!dash || !dash.hashStates || !dash.tabId) return null;
      var bucket = dash.hashStates[dash.tabId];
      var data = bucket && bucket.state;
      if (!data || typeof data !== "object" || Array.isArray(data)) return null;
      return data;
    } catch (e) {
      return null;
    }
  }
  function loadFilters(dashboardId) {
    var live = liveStateData();
    if (live) return Promise.resolve(filtersFromState({data: live}));
    var hash = new URLSearchParams(location.search).get("state");
    if (!dashboardId || !hash) return Promise.resolve({});
    function once(token) {
      return fetch("/gateway/root/us/getDashState", {
        method: "POST",
        credentials: "include",
        headers: {"content-type": "application/json", "x-csrf-token": token || ""},
        body: JSON.stringify({entryId: dashboardId, hash: hash})
      }).then(function (res) {
        var next = res.headers.get("x-csrf-token");
        if (next) cachedCsrf = next;
        if (res.status === 419 && next && next !== token) return once(next);
        if (!res.ok) return {};
        return res.json().then(filtersFromState);
      });
    }
    return once(cachedCsrf).catch(function () { return {}; });
  }
  root.querySelector(".dn-toggle").addEventListener("click", function () { pageContext(); panel.classList.toggle("dn-panel-closed"); });
  root.querySelector(".dn-close").addEventListener("click", function () { panel.classList.add("dn-panel-closed"); });
  root.querySelector(".dn-formula").addEventListener("click", function () {
    if (busy) return;
    formulaMode = !formulaMode;
    applyMode();
  });
  root.querySelector(".dn-new").addEventListener("click", function () {
    if (busy) return;
    call("POST", formulaMode ? "/v1/ui/formula/new" : "/v1/ui/new").then(function (res) { if (res.ok) paint([]); else bubble("assistant", failText(res.status, res.requestId)); });
  });
  field.addEventListener("keydown", function (event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });
  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var text = field.value.trim();
    if (!text || busy) return;
    busy = true;
    field.disabled = true;
    bubble("user", text);
    var pending = bubble("assistant", "Думаю…");
    field.value = "";
    var timer = setInterval(function () {
      call("GET", "/v1/ui/session").then(function (res) { if (res.status === 401) expired = "Обновите страницу DataLens"; });
    }, 15000);
    var page = pageContext();
    var sent;
    if (formulaMode) {
      var formulaPayload = {message: text};
      var chart = formulaContext();
      if (chart) formulaPayload.context = chart;
      sent = call("POST", "/v1/ui/formula", formulaPayload);
    } else {
      sent = loadFilters(page.dashboardId).then(function (params) {
        var names = Object.keys(params);
        if (names.length) {
          page.params = params;
          paintPage(page, names);
        }
        var payload = {message: text};
        if (page.dashboardId || page.chartId) payload.context = page;
        return call("POST", "/v1/ui/chat", payload);
      });
    }
    sent.then(function (res) {
      clearInterval(timer);
      busy = false;
      field.disabled = false;
      if (res.ok) pending.innerHTML = htmlOf(res.body.reply, res.body.sources, res.body.steps);
      else pending.textContent = failText(res.status, res.requestId);
      if (expired) { field.disabled = true; field.placeholder = expired; }
    });
  });
  call("GET", "/v1/ui/session").then(function (session) {
    if (!session.ok || session.body.enabled === false) { root.remove(); return; }
    return applyMode();
  });
})();
