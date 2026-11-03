/* SiteStock offline-first application. Vanilla JS only; every API request is same-origin. */
(() => {
  "use strict";

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const pageView = $("#page-view");
  const networkStrip = $("#network-strip");
  const networkMessage = $("#network-message");
  const today = new Date();
  const state = {
    page: "dashboard",
    catalog: { sites: [], materials: [], customers: [] },
    catalogAll: null,
    siteId: null,
    materialId: null,
    dashboardFilters: null,
    inventoryFilters: { page: 1, page_size: 20, search: "", site_id: "", material_id: "", transaction_type: "", start_date: "", end_date: "" },
    salesFilters: { page: 1, page_size: 20, search: "", site_id: "", material_id: "", start_date: "", end_date: "" },
    forecastSelection: null,
    forecastResult: null,
    forecastModel: null,
    forecastVisibleModels: [],
    forecastLeaderboard: null,
    datasetCoverage: null,
    forecastEligibility: null,
    replenishmentSelection: null,
    replenishmentResult: null,
    suppliers: [],
    data: { uploadFile: null, validation: null, importResult: null },
    reportFilters: null,
  };

  const PAGE_META = {
    dashboard: { crumb: "DASHBOARD", eyebrow: "Site operations", title: "Field overview", description: "A live view of operational stock, customer sales, reorder alerts and separate historical demand indicators." },
    inventory: { crumb: "INVENTORY", eyebrow: "Stock control", title: "Inventory ledger", description: "Post verified physical counts and movements, review current balances and administer the site/material catalogue." },
    sales: { crumb: "SALES", eyebrow: "Commercial activity", title: "Sales & margin", description: "Record stock-consuming sales, keep customer details minimal and report revenue separately from cost-backed margin." },
    forecasting: { crumb: "FORECASTING", eyebrow: "Demand intelligence", title: "Forecast workspace", description: "Compare leakage-aware chronological models and inspect holdout performance before viewing the next periods." },
    replenishment: { crumb: "REPLENISHMENT", eyebrow: "Planning controls", title: "Replenishment planner", description: "Combine live ledger stock, an eligible demand source and an explicit site/material rule using transparent reorder math." },
    purchasing: { crumb: "PURCHASING", eyebrow: "Supplier orders", title: "Purchasing", description: "Create supplier orders from calculated replenishment, track approval, and receive goods into the inventory ledger." },
    reports: { crumb: "DATA & REPORTS", eyebrow: "Audit & exports", title: "Data & reports", description: "Review source quality, validate/import CSV observations and export operational and historical records separately." },
  };

  function localDateString(date = new Date()) {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, "0");
    const d = String(date.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
  }
  const todayString = localDateString(today);
  const monthStartString = localDateString(new Date(today.getFullYear(), today.getMonth(), 1));
  const dateDaysAgo = (n) => localDateString(new Date(Date.now() - n * 86400000));
  const money = (value, digits = 2) => value === null || value === undefined || value === "" || !Number.isFinite(Number(value))
    ? "—"
    : new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", minimumFractionDigits: digits, maximumFractionDigits: digits }).format(Number(value));
  const qty = (value, digits = 2) => value === null || value === undefined || value === "" || !Number.isFinite(Number(value))
    ? "—"
    : new Intl.NumberFormat("en-IN", { maximumFractionDigits: digits }).format(Number(value));
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const opt = (items, valueKey, labelFn, selected = "", placeholder = null) => {
    let html = placeholder === null ? "" : `<option value="">${esc(placeholder)}</option>`;
    html += (items || []).map((item) => {
      const value = String(item[valueKey]);
      return `<option value="${esc(value)}" ${String(selected) === value ? "selected" : ""}>${esc(labelFn(item))}</option>`;
    }).join("");
    return html;
  };
  const activeSites = () => state.catalog.sites.filter((x) => x.is_active);
  const activeMaterials = () => state.catalog.materials.filter((x) => x.is_active);
  const activeCustomers = () => state.catalog.customers.filter((x) => x.is_active);
  const getSite = (id) => state.catalog.sites.find((x) => String(x.id) === String(id)) || (state.catalogAll?.sites || []).find((x) => String(x.id) === String(id));
  const getMaterial = (id) => state.catalog.materials.find((x) => String(x.id) === String(id)) || (state.catalogAll?.materials || []).find((x) => String(x.id) === String(id));
  const numberOrNull = (value) => value === "" || value === null || value === undefined ? null : Number(value);
  const newIdempotencyKey = () => globalThis.crypto?.randomUUID
    ? globalThis.crypto.randomUUID()
    : `ss-${Date.now()}-${Math.random().toString(16).slice(2)}-${Math.random().toString(16).slice(2)}`;
  const selectedSiteId = () => state.siteId && getSite(state.siteId) ? String(state.siteId) : (activeSites()[0] ? String(activeSites()[0].id) : "");
  const selectedMaterialId = () => state.materialId && getMaterial(state.materialId) ? String(state.materialId) : (activeMaterials()[0] ? String(activeMaterials()[0].id) : "");

  class APIError extends Error {
    constructor(message, status, code, details) { super(message); this.name = "APIError"; this.status = status; this.code = code; this.details = details; }
  }

  async function api(path, options = {}) {
    const headers = new Headers(options.headers || {});
    const requestOptions = { ...options, headers, credentials: "same-origin" };
    if (options.body && !(options.body instanceof FormData) && typeof options.body !== "string") {
      headers.set("Content-Type", "application/json");
      requestOptions.body = JSON.stringify(options.body);
    }
    const response = await fetch(path, requestOptions);
    if (response.status === 204) return null;
    const contentType = response.headers.get("content-type") || "";
    const payload = contentType.includes("application/json") ? await response.json() : await response.text();
    if (!response.ok) {
      const error = payload && payload.error ? payload.error : {};
      const details = error.details;
      const extra = Array.isArray(details) ? details.map((x) => x.message || JSON.stringify(x)).join("; ") : "";
      throw new APIError(`${error.message || `Request failed (${response.status})`}${extra ? ` — ${extra}` : ""}`, response.status, error.code, details);
    }
    return payload;
  }

  function setBusy(visible, message = "Loading local data…") {
    networkStrip.classList.toggle("visible", !!visible);
    networkMessage.textContent = message;
  }
  function toast(message, kind = "success") {
    const host = $("#toast-stack");
    const node = document.createElement("div");
    node.className = `toast ${kind}`;
    node.innerHTML = `<span>${kind === "error" ? "!" : kind === "info" ? "i" : "✓"}</span><span>${esc(message)}</span>`;
    host.appendChild(node);
    window.setTimeout(() => node.remove(), 4200);
  }
  function showError(message, target = pageView) {
    const node = document.createElement("div");
    node.className = "error-state";
    node.innerHTML = `<strong>Request could not be completed</strong><br>${esc(message)}`;
    target.prepend(node);
  }
  function badge(text, sales = false) { return `<span class="badge source ${sales ? "sales-source" : ""}">${esc(text)}</span>`; }
  const uiSourceLabel = (label) => label === "Dataset" || !label ? "Construction Materials Dehradun Dataset" : label;
  const coverageLabel = (coverage) => coverage?.from && coverage?.to ? `Covers ${coverage.from} to ${coverage.to}` : "Coverage unavailable";
  function statusClass(text) {
    const s = String(text || "").toLowerCase();
    if (/below|at risk|conflict|stale|unavailable|not initialized|negative|failed|error/.test(s)) return "bad";
    if (/reorder|needs|review|required|partial|not configured|retrospective/.test(s)) return "warn";
    if (/covered|above|available|fully costed|complete|saved|ok/.test(s)) return "good";
    return "neutral";
  }
  function statusPill(text) { return `<span class="status ${statusClass(text)}">${esc(text || "—")}</span>`; }
  function heading(page, tag = "LOCAL OPERATIONS") {
    const meta = PAGE_META[page];
    $("#crumb-page").textContent = meta.crumb;
    return `<div class="page-heading"><div><div class="eyebrow">${esc(meta.eyebrow)}</div><h1>${esc(meta.title)}</h1><p class="page-description">${esc(meta.description)}</p></div><div class="page-tag">${esc(tag)}</div></div>`;
  }
  function emptyState(title, detail) {
    return `<div class="empty-state"><div><div class="empty-icon">⌑</div><strong>${esc(title)}</strong><p>${esc(detail || "No records match this view yet.")}</p></div></div>`;
  }
  function card(label, value, meta = "", accent = "", small = false) {
    return `<div class="kpi-card kpi-accent ${accent}"><div class="kpi-label">${esc(label)}</div><div class="kpi-value ${small ? "small-value" : ""}">${value}</div><div class="kpi-meta">${meta}</div></div>`;
  }
  function table(headers, rows, emptyTitle = "No records", emptyDetail = "") {
    if (!rows || !rows.length) return emptyState(emptyTitle, emptyDetail);
    return `<div class="table-wrap"><table><thead><tr>${headers.map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody></table></div>`;
  }
  function pageLoading() {
    pageView.innerHTML = `<div class="loading-state"><span class="spinner"></span><span>Loading local records…</span></div>`;
  }
  async function loadCatalog(includeInactive = false) {
    const result = await api(`/api/catalog${includeInactive ? "?include_inactive=true" : ""}`);
    if (includeInactive) state.catalogAll = result;
    else state.catalog = result;
    if (!includeInactive) {
      if (!activeSites().some((x) => String(x.id) === String(state.siteId))) state.siteId = activeSites()[0]?.id ?? null;
      if (!activeMaterials().some((x) => String(x.id) === String(state.materialId))) state.materialId = activeMaterials()[0]?.id ?? null;
    }
    return result;
  }

  function plot(id, traces, yTitle = "", options = {}) {
    const element = document.getElementById(id);
    if (!element) return;
    if (!window.Plotly) { element.classList.add("empty-chart"); element.textContent = "Chart library is not available in this local copy."; return; }
    const layout = {
      autosize: true,
      height: options.height || 270,
      margin: { l: 52, r: 16, t: 12, b: 43 },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      font: { family: "system-ui, sans-serif", size: 10, color: "#969f9a" },
      legend: { orientation: "h", y: -0.28, x: 0, font: { size: 9, color: "#a8b0ab" } },
      xaxis: { gridcolor: "#29302e", linecolor: "#3a4240", zerolinecolor: "#3a4240", tickfont: { color: "#848d88" }, automargin: true, ...(options.xaxis || {}) },
      yaxis: { title: yTitle ? { text: yTitle, font: { size: 9, color: "#8d9691" } } : undefined, gridcolor: "#29302e", linecolor: "#3a4240", zerolinecolor: "#3a4240", tickfont: { color: "#848d88" }, automargin: true },
      hovermode: "x unified",
    };
    window.Plotly.react(element, traces, layout, { displayModeBar: false, responsive: true, scrollZoom: false });
  }
  function makeOptionGroups(items, selected, by = "identifier") {
    return opt(items, "id", (x) => x[by] || x.name || "", selected);
  }
  function siteSelect(name, selected, sites = activeSites(), label = "Project site") {
    return `<div class="field"><label for="${esc(name)}">${esc(label)}</label><select id="${esc(name)}" name="site_id" required>${makeOptionGroups(sites, selected, "identifier")}</select></div>`;
  }
  function materialSelect(name, selected, materials = activeMaterials(), label = "Material") {
    return `<div class="field"><label for="${esc(name)}">${esc(label)}</label><select id="${esc(name)}" name="material_id" required>${makeOptionGroups(materials, selected, "name")}</select></div>`;
  }
  function encodeQuery(values) {
    const params = new URLSearchParams();
    Object.entries(values).forEach(([key, value]) => { if (value !== "" && value !== null && value !== undefined) params.set(key, value); });
    return params.toString();
  }
  function catalogCheck() {
    if (!activeSites().length || !activeMaterials().length) {
      pageView.innerHTML = `${heading(state.page)}${emptyState("Catalogue is empty", "Add an active project site and material in Inventory before recording operations.")}`;
      return false;
    }
    return true;
  }

  async function renderDashboard() {
    const sites = activeSites();
    const materials = activeMaterials();
    const siteId = String(state.dashboardFilters?.site_id || selectedSiteId() || "");
    const materialId = String(state.dashboardFilters?.material_id || selectedMaterialId() || "");
    const start = state.dashboardFilters?.start_date || monthStartString;
    const end = state.dashboardFilters?.end_date || todayString;
    const query = encodeQuery({ site_id: siteId, material_id: materialId, start_date: start, end_date: end });
    const [data, leaderboard] = await Promise.all([
      api(`/api/dashboard?${query}`),
      api("/api/forecasts/leaderboard").catch((error) => ({ items: [], wins: [], error: error.message })),
    ]);
    state.dashboardFilters = { site_id: siteId, material_id: materialId, start_date: start, end_date: end };
    const summary = data.summary;
    const alertRows = data.alerts.map((item) => `<div class="alert-row"><div><strong>${esc(item.material)} <span class="muted">/ ${esc(item.site)}</span></strong><span>${qty(item.current_stock)} ${esc(item.unit)} on hand · reorder at ${qty(item.reorder_point_qty)} ${esc(item.unit)}</span></div>${statusPill(item.status)}</div>`);
    const riskRows = (data.inventory_risk || []).map((item) => `<tr><td>${esc(item.site)}</td><td><strong>${esc(item.material)}</strong></td><td>${item.stock == null ? "Needs physical count" : `${qty(item.stock)} ${esc(item.unit)}`}</td><td>${item.days_of_cover == null ? "—" : `${qty(item.days_of_cover,0)} days`}</td><td>${statusPill(item.risk_level)}${item.overstock ? `<br>${statusPill("Overstock")}` : ""}</td><td>${esc(item.suggestion)}${item.suggested_qty > 0 ? ` · ${qty(item.suggested_qty)} ${esc(item.unit)}` : ""}</td></tr>`);
    const valueText = summary.all_pairs_recorded_stock_value_inr === null ? "Unavailable" : money(summary.all_pairs_recorded_stock_value_inr, 0);
    const marginText = summary.gross_margin_inr === null ? "Unavailable" : money(summary.gross_margin_inr);
    const coverage = data.historical_coverage;
    const leaderboardWins = [...(leaderboard.wins || [])].sort((a,b) => b.wins-a.wins || a.model.localeCompare(b.model));
    const leaderboardRows = (leaderboard.items || []).slice(0,8).map((item) => `<tr><td>${esc(item.site)}</td><td>${esc(item.material)}</td><td><strong>${esc(item.best_model)}</strong></td><td class="numeric">${qty(item.best_mae,2)} ${esc(item.unit)}</td></tr>`);
    const leaderboardWinRows = leaderboardWins.map((item) => `<tr><td>${esc(item.model)}</td><td class="numeric"><strong>${qty(item.wins,0)}</strong></td></tr>`);
    const topMaterialRows = (data.top_materials || []).map((item) => `<tr><td><strong>${esc(item.material)}</strong></td><td class="numeric">${qty(item.quantity,2)} ${esc(item.unit)}</td><td class="numeric">${money(item.revenue_inr)}</td><td class="numeric">${qty(item.sale_count,0)}</td></tr>`);
    pageView.innerHTML = `${heading("dashboard", "LIVE LEDGER + HISTORICAL CONTEXT")}
      <form class="page-toolbar" id="dashboard-filter-form"><div class="toolbar-fields">
        <div class="field"><label for="dash-site">Site focus</label><select id="dash-site" name="site_id">${makeOptionGroups(sites, siteId, "identifier")}</select></div>
        <div class="field"><label for="dash-material">Material focus</label><select id="dash-material" name="material_id">${makeOptionGroups(materials, materialId, "name")}</select></div>
        <div class="field"><label for="dash-start">Reporting from</label><input id="dash-start" type="date" name="start_date" value="${esc(start)}" max="${todayString}" required></div>
        <div class="field"><label for="dash-end">Reporting to</label><input id="dash-end" type="date" name="end_date" value="${esc(end)}" max="${todayString}" required></div>
      </div><button class="button primary" type="submit">Apply view</button></form>
      <div class="kpi-grid">
        ${card("Initialized stock lines", qty(summary.all_pairs_initialized, 0), "Across the active site/material catalogue", "")}
        ${card("Recorded stock value", valueText, esc(summary.all_pairs_stock_value_status), "teal-top", true)}
        ${card("Low-stock lines", qty(summary.all_pairs_low_stock, 0), "At or below configured reorder points", summary.all_pairs_low_stock ? "red-top" : "")}
        ${card("Out-of-stock lines", qty(summary.all_pairs_out_of_stock, 0), "Initialized balances at zero or below", summary.all_pairs_out_of_stock ? "red-top" : "")}
        ${card("High / medium / low risk", `${summary.risk_high} / ${summary.risk_medium} / ${summary.risk_low}`, `${summary.risk_pairs} active pairs · ${summary.risk_overstock} overstock`, summary.risk_high ? "red-top" : "teal-top", true)}
        ${card("Sales in period", qty(summary.sales_count, 0), `${esc(start)} through ${esc(end)}`, "blue-top")}
        ${card("Revenue", money(summary.sales_revenue_inr,0), "Posted sales in the selected period", "blue-top")}
        ${card("Gross margin", marginText, esc(summary.margin_status), summary.gross_margin_inr === null ? "red-top" : "teal-top", true)}
      </div>
      <div class="content-grid equal">
        <section class="panel"><div class="panel-header"><div><h2 class="panel-title">Unified inventory risk</h2><p class="panel-subtitle">High ${summary.risk_high} · Medium ${summary.risk_medium} · Low ${summary.risk_low}; counts cover all active pairs.</p></div><a href="#" class="button small" data-page="replenishment">Open planner</a></div><div class="panel-body compact">${table(["Site","Material","Live stock","Cover","Risk","Next action"],riskRows,"No active inventory pairs","Risk is computed with the shared policy. Missing physical counts are marked High.")}</div><div class="chart-note">${esc(data.inventory_risk_method)}</div></section>
        <section class="panel"><div class="panel-header"><div><h2 class="panel-title">Dataset consumption</h2><p class="panel-subtitle">${badge("Dataset")} · monthly observed quantities · ${esc(data.selection.material || "No material")} (${esc(data.selection.unit || "unit")})</p></div><span class="inline-code">SOURCE</span></div><div class="chart-wrap"><div class="chart" id="dashboard-history-chart"></div></div><div class="chart-note">${coverage ? `Covers ${esc(coverage.from)} to ${esc(coverage.to)} · ${qty(coverage.observations,0)} observations.` : "No observations for this selection."} Missing calendar periods remain missing, not zero.</div></section>
        <section class="panel"><div class="panel-header"><div><h2 class="panel-title">Operational sales revenue</h2><p class="panel-subtitle">Posted sales only · INR · reported separately from historical consumption.</p></div>${badge("Operational sales", true)}</div><div class="chart-wrap"><div class="chart" id="dashboard-sales-chart"></div></div><div class="chart-note">Sales in the current filter window: ${esc(start)} through ${esc(end)}.</div></section>
      </div>
      <div class="content-grid equal">
        <section class="panel"><div class="panel-header"><div><h2 class="panel-title">Reorder alerts</h2><p class="panel-subtitle">Live ledger balance at or below an active site/material threshold.</p></div><a href="#" class="button small" data-page="replenishment">Open planner</a></div><div class="panel-body"><div class="alert-list">${alertRows.length ? alertRows.join("") : `<div class="empty-state"><div><strong>No active reorder alerts</strong><p>Configure a site/material reorder point to enable operational alerts.</p></div></div>`}</div></div></section>
        <section class="panel"><div class="panel-header"><div><h2 class="panel-title">Source integrity</h2><p class="panel-subtitle">Dataset observations and operations remain separate.</p></div><span class="status good">Separated</span></div><div class="panel-body"><div class="method-box"><span class="callout-title">Dataset observations</span> do not initialize stock or create operational transactions.<br><br><span class="callout-title">Operational sales</span> feed revenue and margin reporting; this forecasting view uses the dataset only.</div><div class="button-row" style="margin-top:12px"><button class="button" data-page="inventory">Open inventory</button><button class="button" data-page="sales">Record sale</button></div></div></section>
      </div>
      <div class="content-grid equal">
        <section class="panel"><div class="panel-header"><div><h2 class="panel-title">Top materials</h2><p class="panel-subtitle">By posted revenue · ${esc(start)} through ${esc(end)}.</p></div></div><div class="panel-body compact">${table(["Material","Quantity","Revenue","Bills"],topMaterialRows,"No sales in this period","Posted sales appear here; no revenue is inferred from dataset prices.")}</div></section>
        <section class="panel"><div class="panel-header"><div><h2 class="panel-title">Model leaderboard</h2><p class="panel-subtitle">Best stored model per site/material pair, selected by pre-holdout rolling-origin MAE.</p></div><a href="#" class="button small" data-page="forecasting">Open forecasting</a></div><div class="panel-body"><div class="method-box"><strong>${qty(leaderboard.pair_count || 0,0)}</strong> current series with saved metrics · leaderboard is computed from stored pre-holdout rolling-origin MAE values only.</div><div class="fields-grid cols-2" style="margin-top:10px"><div>${table(["Model","Pair wins"],leaderboardWinRows,"No stored evaluations","Run the offline model-training command to populate this comparison.")}</div><div>${table(["Site","Material","Best model","MAE"],leaderboardRows,"No stored evaluations","No metrics match the current dataset hash.")}</div></div></div></section>
      </div>`;
    plot("dashboard-history-chart", [{ x: data.historical_consumption_trend.map((x) => x.period), y: data.historical_consumption_trend.map((x) => x.quantity), type: "scatter", mode: "lines+markers", name: "Observed", line: { color: "#D9A441", width: 2 }, marker: { color: "#D9A441", size: 5 }, connectgaps: false }], data.selection.unit || "Quantity", { height: 245 });
    plot("dashboard-sales-chart", [{ x: data.operational_sales_revenue_trend.map((x) => x.period), y: data.operational_sales_revenue_trend.map((x) => x.revenue_inr), type: "bar", name: "Sales revenue", marker: { color: "#41B8AA" } }], "Revenue (INR)", { height: 245, xaxis: { type: "category", tickangle: 0 } });
  }

  function inventoryTableRows(items) {
    return items.map((x) => `<tr><td>${esc(x.site)}</td><td><strong>${esc(x.material)}</strong></td><td class="numeric">${qty(x.current_usable_stock)}</td><td>${esc(x.unit)}</td><td>${statusPill(x.stock_status)}</td><td>${x.reorder_point_qty === null ? `<span class="muted">—</span>` : `${qty(x.reorder_point_qty)} ${esc(x.unit)}`}<span class="subcell">${statusPill(x.reorder_status)}</span></td><td class="numeric">${x.recorded_stock_value_inr === null ? `<span class="muted">—</span>` : money(x.recorded_stock_value_inr)}</td><td>${statusPill(x.cost_basis_status)}</td></tr>`);
  }
  function ledgerRows(items) {
    return items.map((x) => `<tr><td class="nowrap">${esc(x.date)}</td><td>${esc(x.site)}</td><td><strong>${esc(x.material)}</strong></td><td>${statusPill(x.type)}</td><td class="numeric">${qty(x.quantity)} ${esc(x.unit)}</td><td class="numeric">${x.unit_cost_inr === null ? `<span class="muted">—</span>` : money(x.unit_cost_inr)}</td><td>${esc(x.reference || "—")}</td><td class="muted">${esc(x.notes || x.source || "—")}</td></tr>`);
  }
  function pagination(total, page, pages, actionName) {
    return `<div class="pagination"><span>${total ? `Showing page ${page} of ${pages} · ${total} record(s)` : "No matching records"}</span><div class="pagination-actions"><button class="button small" data-action="${actionName}-page" data-page-number="${Math.max(1, page - 1)}" ${page <= 1 ? "disabled" : ""}>Previous</button><button class="button small" data-action="${actionName}-page" data-page-number="${Math.min(pages || 1, page + 1)}" ${page >= pages ? "disabled" : ""}>Next</button></div></div>`;
  }
  function createTransactionForm() {
    const sites = activeSites();
    const materials = activeMaterials();
    const siteId = selectedSiteId();
    const materialId = selectedMaterialId();
    const material = getMaterial(materialId);
    return `<section class="form-panel"><div class="form-panel-header"><h2>Post stock movement</h2><p>Receipts and consumption require a physical opening count. Unit costs are optional recorded values; no CSV prices are copied.</p></div><div class="form-panel-body"><form id="transaction-form" class="form-section"><input type="hidden" name="idempotency_key" value="${newIdempotencyKey()}">
      <div class="fields-grid cols-3">
        ${siteSelect("txn-site", siteId, sites)}
        ${materialSelect("txn-material", materialId, materials)}
        <div class="field"><label for="txn-kind">Movement type</label><select id="txn-kind" name="transaction_type" required><option value="opening_balance">Physical opening count</option><option value="receipt">Receipt</option><option value="consumption">Consumption</option><option value="adjustment">Stock adjustment</option></select></div>
      </div>
      <div class="fields-grid cols-4">
        <div class="field"><label for="txn-quantity">Quantity (${esc(material?.unit || "unit")})</label><input id="txn-quantity" name="quantity" type="number" step="0.0001" min="0.0001" value="" placeholder="Enter quantity" required><small>Adjustments may be positive or negative; other movements must be positive.</small></div>
        <div class="field"><label for="txn-unit">Unit</label><input id="txn-unit" type="text" value="${esc(material?.unit || "")}" readonly><small>Unit is fixed by the material catalogue.</small></div>
        <div class="field"><label for="txn-date">Transaction date</label><input id="txn-date" name="transaction_date" type="date" value="${todayString}" max="${todayString}" required></div>
        <div class="field"><label for="txn-reference">Reference (optional)</label><input id="txn-reference" name="reference" maxlength="120" placeholder="Receipt / count reference"></div>
      </div>
      <div class="fields-grid cols-3">
        <div class="field cost-field"><label for="txn-unit-cost">Recorded unit cost (INR, optional)</label><input id="txn-unit-cost" name="unit_cost_inr" type="number" step="0.0001" min="0" placeholder="Leave blank if unknown"><small>Only actual recorded inventory cost supports stock value and sale margin.</small></div>
        <div class="field adjustment-field hidden"><label for="txn-reason">Adjustment reason <span class="text-danger">required</span></label><input id="txn-reason" name="reason" maxlength="500" placeholder="Explain the count correction"></div>
        <div class="field notes-field"><label for="txn-notes">Notes (optional)</label><input id="txn-notes" name="notes" maxlength="1000" placeholder="Additional context"></div>
      </div>
      <div class="form-footer"><span class="field-help">Duplicate requests are rejected by idempotency key. Negative stock and future dates are blocked.</span><button class="button primary" type="submit">Post movement</button></div>
    </form></div></section>`;
  }
  function adminPanels() {
    const all = state.catalogAll || state.catalog;
    const sites = all.sites || [];
    const materials = all.materials || [];
    const siteId = String(state.adminSiteId || sites[0]?.id || "");
    const materialId = String(state.adminMaterialId || materials[0]?.id || "");
    const site = sites.find((x) => String(x.id) === siteId) || {};
    const material = materials.find((x) => String(x.id) === materialId) || {};
    state.adminSiteId = siteId;
    state.adminMaterialId = materialId;
    const siteRows = sites.map((x) => `<div class="admin-row"><div><strong>${esc(x.identifier)}</strong><small>${esc(x.name)} · ${esc(x.city)}, ${esc(x.state)}</small></div><button class="toggle-active" data-action="toggle-site" data-id="${x.id}" data-active="${x.is_active}">${x.is_active ? "Deactivate" : "Activate"}</button></div>`).join("");
    const materialRows = materials.map((x) => `<div class="admin-row"><div><strong>${esc(x.name)} <span class="muted">(${esc(x.unit)})</span></strong><small>${x.default_lead_time_days ? `${x.default_lead_time_days} day lead` : "Lead time unset"} · legacy setting ${x.safety_stock_days} days</small></div><button class="toggle-active" data-action="toggle-material" data-id="${x.id}" data-active="${x.is_active}">${x.is_active ? "Deactivate" : "Activate"}</button></div>`).join("");
    return `<div class="section-heading"><div><h2>Catalogue administration</h2><p>Add or update site/material records; deactivate instead of deleting referenced records.</p></div></div>
      <div class="content-grid equal">
       <section class="panel"><div class="panel-header"><div><h2 class="panel-title">Project sites</h2><p class="panel-subtitle">Stable identifiers preserve source and transaction traceability.</p></div></div><div class="panel-body">
        <form id="site-create-form" class="form-section"><div class="fields-grid"><div class="field"><label>Site identifier</label><input name="identifier" required maxlength="160" placeholder="e.g. North Yard"></div><div class="field"><label>Display name</label><input name="name" required maxlength="160" placeholder="Site name"></div><div class="field"><label>City</label><input name="city" required maxlength="100"></div><div class="field"><label>State</label><input name="state" required maxlength="100"></div></div><button class="button primary" type="submit">Add site</button></form>
        <div class="section-rule"></div><div class="field"><label>Update selected site</label><select id="site-admin-select">${opt(sites,"id",(x)=>`${x.identifier} · ${x.city}`,siteId)}</select></div>
        <form id="site-update-form" class="form-section" style="margin-top:10px"><div class="fields-grid"><div class="field"><label>Display name</label><input name="name" value="${esc(site.name)}" required></div><div class="field"><label>City</label><input name="city" value="${esc(site.city)}" required></div><div class="field"><label>State</label><input name="state" value="${esc(site.state)}" required></div><div class="field"><label>Project type</label><input name="project_type" value="${esc(site.project_type)}"></div></div><input type="hidden" name="site_id" value="${esc(siteId)}"><button class="button small" type="submit">Save site details</button></form>
       </div><div class="panel-body compact">${siteRows || emptyState("No project sites", "Create a site to begin.")}</div></section>
       <section class="panel"><div class="panel-header"><div><h2 class="panel-title">Materials</h2><p class="panel-subtitle">Units are immutable after use in source or operational transactions.</p></div></div><div class="panel-body">
        <form id="material-create-form" class="form-section"><div class="fields-grid"><div class="field"><label>Material name</label><input name="name" required maxlength="120" placeholder="e.g. Aggregate"></div><div class="field"><label>Unit</label><input name="unit" required maxlength="40" placeholder="e.g. tonnes"></div></div><button class="button primary" type="submit">Add material</button></form>
        <div class="section-rule"></div><div class="field"><label>Update selected material</label><select id="material-admin-select">${opt(materials,"id",(x)=>`${x.name} · ${x.unit}`,materialId)}</select></div>
        <form id="material-update-form" class="form-section" style="margin-top:10px"><div class="fields-grid cols-3"><div class="field"><label>Name</label><input name="name" value="${esc(material.name)}" required></div><div class="field"><label>Unit</label><input name="unit" value="${esc(material.unit)}" required></div><div class="field"><label>Default lead time (days)</label><input name="default_lead_time_days" type="number" min="1" max="365" value="${esc(material.default_lead_time_days)}"></div><div class="field"><label>Legacy safety days (not used by risk)</label><input name="safety_stock_days" type="number" min="0" max="90" value="${esc(material.safety_stock_days ?? 7)}"></div><div class="field"><label>Minimum order qty</label><input name="minimum_order_qty" type="number" min="0" step="0.0001" value="${esc(material.minimum_order_qty ?? 0)}"></div><div class="field"><label>Order multiple</label><input name="order_multiple" type="number" min="0" step="0.0001" value="${esc(material.order_multiple ?? 0)}"></div><div class="field"><label>Maximum stock qty</label><input name="maximum_stock_qty" type="number" min="0" step="0.0001" value="${esc(material.maximum_stock_qty)}"></div><div class="field"><label>Reference unit price (INR)</label><input name="benchmark_unit_price_inr" type="number" min="0" step="0.0001" value="${esc(material.benchmark_unit_price_inr)}"><small>Reference only; never used for sales margin or recorded stock value.</small></div><label class="checkbox-row"><input name="is_active" type="checkbox" ${material.is_active ? "checked" : ""}> Active</label></div><input type="hidden" name="material_id" value="${esc(materialId)}"><button class="button small" type="submit">Save material details</button></form>
       </div><div class="panel-body compact">${materialRows || emptyState("No materials", "Create a material to begin.")}</div></section>
      </div>`;
  }

  async function renderInventory() {
    if (!catalogCheck()) return;
    await loadCatalog(true);
    const all = state.catalogAll;
    const invf = state.inventoryFilters;
    const balancesQuery = encodeQuery({ site_id: invf.site_id, material_id: invf.material_id, alert_only: false, search: invf.search });
    const txQuery = encodeQuery({ page: invf.page, page_size: invf.page_size, search: invf.search, site_id: invf.site_id, material_id: invf.material_id, transaction_type: invf.transaction_type, start_date: invf.start_date, end_date: invf.end_date });
    const [balanceData, ledger] = await Promise.all([
      api(`/api/inventory/balances?${balancesQuery}`),
      api(`/api/inventory/transactions?${txQuery}`),
    ]);
    const initialized = balanceData.items.filter((x) => x.current_usable_stock !== null);
    const alertCount = balanceData.items.filter((x) => x.reorder_alert).length;
    const completeValue = initialized.length > 0 && initialized.every((x) => x.cost_basis_status === "Fully costed");
    const stockValue = completeValue ? money(initialized.reduce((s, x) => s + Number(x.recorded_stock_value_inr || 0), 0), 0) : "Unavailable";
    const siteOpts = all.sites || [];
    const materialOpts = all.materials || [];
    const inventoryExport = `/api/reports/ledger.csv?${encodeQuery({ site_id: invf.site_id, material_id: invf.material_id, start_date: invf.start_date, end_date: invf.end_date, search: invf.search })}`;
    const balanceRows = inventoryTableRows(balanceData.items);
    const typeValue = invf.transaction_type;
    pageView.innerHTML = `${heading("inventory", "LIVE STOCK LEDGER")}
      <div class="kpi-grid">${card("Catalogued pairs", qty(balanceData.total,0), "Site/material balances remain unit-specific")}${card("Initialized balances", qty(initialized.length,0), "Require an explicit physical opening count", "teal-top")}${card("Reorder alerts", qty(alertCount,0), "At or below configured reorder point", alertCount ? "red-top" : "")}${card("Recorded stock value", stockValue, completeValue ? "Recorded FIFO costs cover all selected stock" : "Uncosted quantity is not assigned a value", "blue-top", true)}</div>
      <div class="content-grid equal">${createTransactionForm()}<section class="panel"><div class="panel-header"><div><h2 class="panel-title">Posting controls</h2><p class="panel-subtitle">Stock ledger integrity</p></div><span class="status good">Operational</span></div><div class="panel-body"><ul class="info-list"><li>Opening count is a verified physical balance, never copied from the CSV.</li><li>Receipts and consumption are rejected until an opening balance exists.</li><li>Negative stock, unit mismatch and future dates are blocked.</li><li>Every adjustment needs a reason and a non-zero signed quantity.</li><li>Unit cost is optional. Unknown cost remains unavailable; reference prices are not used.</li><li>Sales appear in this ledger as stock-consuming sale movements.</li></ul><div class="section-rule"></div><div class="method-box"><span class="callout-title">Balance</span> = opening count + receipts − consumption ± signed adjustments.<br><span class="callout-title">Valuation</span> uses only recorded cost layers; if any remaining units lack cost, total stock value is shown as unavailable.</div></div></section></div>
      ${adminPanels()}
      <div class="section-heading"><div><h2>Current stock by site &amp; material</h2><p>Historical inventory fields are not current stock. Uninitialized balances are blank, not zero.</p></div><a class="button small" href="/api/reports/current-inventory.csv" download>Export balances CSV</a></div>
      ${table(["Site","Material","On hand","Unit","Ledger status","Reorder point / alert","Recorded value","Cost basis"], balanceRows, "No catalogue pairs", "Add an active site and material to manage balances.")}
      <div class="section-heading"><div><h2>Transaction ledger</h2><p>Searchable, filterable, paginated operational movements.</p></div><a class="button small" href="${inventoryExport}" download>Export filtered ledger</a></div>
      <form id="inventory-filter-form" class="filter-row"><div class="field search-field"><label>Search</label><input name="search" value="${esc(invf.search)}" placeholder="Site, material, reference or reason"></div><div class="field"><label>Site</label><select name="site_id">${opt(siteOpts,"id",(x)=>x.identifier,invf.site_id,"All sites")}</select></div><div class="field"><label>Material</label><select name="material_id">${opt(materialOpts,"id",(x)=>x.name,invf.material_id,"All materials")}</select></div><div class="field"><label>Movement</label><select name="transaction_type"><option value="">All types</option>${["opening_balance","receipt","consumption","adjustment","sale"].map((x)=>`<option value="${x}" ${typeValue===x?"selected":""}>${x.replaceAll("_"," ").replace(/\b\w/g,(m)=>m.toUpperCase())}</option>`).join("")}</select></div><div class="field"><label>From</label><input name="start_date" type="date" value="${esc(invf.start_date)}" max="${todayString}"></div><div class="field"><label>To</label><input name="end_date" type="date" value="${esc(invf.end_date)}" max="${todayString}"></div><button class="button" type="submit">Filter</button></form>
      ${table(["Date","Site","Material","Movement","Quantity","Recorded unit cost","Reference","Notes / source"], ledgerRows(ledger.items), "No transactions yet", "Post an opening physical count before receipts or consumption.")}
      ${pagination(ledger.total, ledger.page, ledger.pages, "inventory")}
      <div class="section-heading"><div><h2>Source boundary</h2><p>CSV observations and current operational ledger are separate in the database and all exports.</p></div></div>`;
    bindUnitFromMaterial($("#transaction-form"));
    updateTransactionFields();
    fillAdminForms();
  }

  function saleRows(items) {
    return items.map((x) => `<tr><td class="nowrap">${esc(x.sale_date)}</td><td>${esc(x.site)}</td><td><strong>${esc(x.material)}</strong><span class="subcell">${qty(x.quantity)} ${esc(x.unit)}</span></td><td>${esc(x.customer || "—")}</td><td class="numeric">${money(x.unit_sale_price_inr)}</td><td class="numeric">${money(x.revenue_inr)}</td><td class="numeric">${x.gross_margin_inr === null ? `<span class="muted">Unavailable</span>` : money(x.gross_margin_inr)}</td><td>${statusPill(x.margin_status)}</td><td>${esc(x.reference || "—")}</td></tr>`);
  }
  async function renderSales() {
    if (!catalogCheck()) return;
    const f = state.salesFilters;
    const start = f.start_date || dateDaysAgo(364);
    const end = f.end_date || todayString;
    state.salesFilters.start_date = start;
    state.salesFilters.end_date = end;
    const query = encodeQuery({ page: f.page, page_size: f.page_size, search: f.search, site_id: f.site_id, material_id: f.material_id, start_date: start, end_date: end });
    const data = await api(`/api/sales?${query}`);
    const s = data.summary;
    const salesExport = `/api/reports/sales.csv?${encodeQuery({ site_id:f.site_id, material_id:f.material_id, start_date:start, end_date:end, search:f.search })}`;
    const sites = state.catalog.sites;
    const materials = state.catalog.materials;
    const customers = state.catalog.customers;
    const material = getMaterial(selectedMaterialId());
    pageView.innerHTML = `${heading("sales", "POSTED CUSTOMER SALES")}
      <div class="kpi-grid">${card("Revenue", money(s.revenue_inr), `${s.sale_count} sale(s) in selected filter`, "blue-top")}${card("Gross margin", s.gross_margin_inr === null ? "Unavailable" : money(s.gross_margin_inr), esc(s.margin_status), s.gross_margin_inr === null ? "red-top" : "teal-top", true)}${card("Costed sales", qty(s.costed_sales_count,0), "All sold units had recorded FIFO cost", "teal-top")}${card("Margin unavailable", qty(s.margin_unavailable_sales_count,0), "No cost fabricated from reference prices", s.margin_unavailable_sales_count ? "red-top" : "")}</div>
      <div class="content-grid equal">
       <section class="form-panel"><div class="form-panel-header"><h2>Record a sale</h2><p>A sale consumes operational stock and reports margin only when its complete FIFO cost is recorded.</p></div><div class="form-panel-body"><form id="sale-form" class="form-section"><input type="hidden" name="idempotency_key" value="${newIdempotencyKey()}">
        <div class="fields-grid cols-3">${siteSelect("sale-site", selectedSiteId(), sites)}${materialSelect("sale-material", selectedMaterialId(), materials)}<div class="field"><label>Customer (optional)</label><select name="customer_id"><option value="">No customer selected</option>${opt(customers,"id",(x)=>x.name)}</select></div></div>
        <div class="fields-grid cols-4"><div class="field"><label>Quantity (${esc(material?.unit || "unit")})</label><input name="quantity" type="number" min="0.0001" step="0.0001" required placeholder="Quantity"></div><div class="field"><label>Unit</label><input name="unit_display" type="text" value="${esc(material?.unit || "")}" readonly></div><div class="field"><label>Sale date</label><input name="sale_date" type="date" value="${todayString}" max="${todayString}" required></div><div class="field"><label>Unit sale price (INR)</label><input name="unit_sale_price_inr" type="number" min="0" step="0.0001" required placeholder="Recorded price"></div></div>
        <div class="fields-grid"><div class="field"><label>Reference (optional)</label><input name="reference" maxlength="120" placeholder="Invoice / sales reference"></div><div class="field"><label>Notes (optional)</label><input name="notes" placeholder="Additional detail"></div></div>
        <div class="alert-box info"><span class="alert-icon">i</span><span>Margin = recorded sale revenue − FIFO cost of sold stock. If the stock's cost layer is unknown, margin is marked unavailable; historical CSV prices are never substituted.</span></div>
        <div class="form-footer"><span class="field-help">Sale posting is idempotent and rejects unit mismatches, future dates and negative stock.</span><button class="button primary" type="submit">Post sale</button></div>
       </form></div></section>
       <section class="panel"><div class="panel-header"><div><h2 class="panel-title">Customer directory</h2><p class="panel-subtitle">Minimal customer records; customer selection on a sale is optional.</p></div></div><div class="panel-body"><form id="customer-form" class="form-section"><div class="fields-grid"><div class="field"><label>Customer name</label><input name="name" required maxlength="160" placeholder="Customer / account name"></div><div class="field"><label>Email (optional)</label><input name="email" type="email" maxlength="160"></div><div class="field"><label>Contact (optional)</label><input name="contact_name" maxlength="120"></div><div class="field"><label>Phone (optional)</label><input name="phone" maxlength="60"></div></div><button class="button" type="submit">Add customer</button></form><div class="section-rule"></div><p class="panel-subtitle">Existing customers: ${customers.length ? customers.map((x)=>`<span class="inline-code">${esc(x.name)}</span>`).join(" ") : "none yet"}</p></div></section>
      </div>
      <div class="section-heading"><div><h2>Sales register</h2><p>Revenue is operational. Margin totals remain unavailable if any filtered sale lacks complete cost basis.</p></div><a class="button small" href="${salesExport}" download>Export filtered sales CSV</a></div>
      <form id="sales-filter-form" class="filter-row"><div class="field search-field"><label>Search</label><input name="search" value="${esc(f.search)}" placeholder="Customer, site, material, reference"></div><div class="field"><label>Site</label><select name="site_id">${opt(sites,"id",(x)=>x.identifier,f.site_id,"All sites")}</select></div><div class="field"><label>Material</label><select name="material_id">${opt(materials,"id",(x)=>x.name,f.material_id,"All materials")}</select></div><div class="field"><label>From</label><input name="start_date" type="date" value="${esc(start)}" max="${todayString}"></div><div class="field"><label>To</label><input name="end_date" type="date" value="${esc(end)}" max="${todayString}"></div><button class="button" type="submit">Filter</button></form>
      ${table(["Date","Site","Material / qty","Customer","Sale price / unit","Revenue","Gross margin","Margin status","Reference"], saleRows(data.items), "No sales recorded", "Post a sale after the relevant site/material ledger has a physical opening balance.")}
      ${pagination(data.total, data.page, data.pages, "sales")}`;
    bindUnitFromMaterial($("#sale-form"));
  }

  function forecastResultView(result) {
    const successful = result.metrics.filter((row) => row.status === "available");
    const chosen = state.forecastModel && result.forecasts[state.forecastModel] ? state.forecastModel : result.best_model;
    state.forecastModel = chosen;
    let visible = state.forecastVisibleModels.filter((name) => result.forecasts[name]);
    if (!visible.length) visible = [chosen];
    state.forecastVisibleModels = visible;
    const bestMetric = result.metrics.find((row) => row.model === result.best_model) || result.metrics[0] || {};
    const naiveScore = result.metrics.find((row) => row.model === "Naive")?.selection_mae;
    const metrics = result.metrics.map((row) => {
      const selected = row.model === result.best_model;
      const reason = selected ? (row.model === "Naive" && naiveScore != null ? "Selected: lowest eligible rolling-origin MAE; fallback baseline." : "Selected: lowest rolling-origin MAE before holdout.") : row.status !== "available" ? (row.message || "Unavailable") : row.selection_mae == null ? "No rolling score" : `Not selected; rolling MAE ${qty(row.selection_mae,2)}${naiveScore != null && row.model !== "Naive" && row.selection_mae >= naiveScore ? " (did not beat Naive)" : ""}.`;
      return `<tr class="${selected ? "best-model-row" : ""}"><td><strong>${esc(row.model)}</strong>${selected ? ` <span class="status good">Selected</span>` : ""}</td><td class="numeric metric-headline">${row.wape_pct == null ? "—" : `${qty(row.wape_pct,2)}%`}</td><td class="numeric">${row.mase == null ? "—" : qty(row.mase,3)}</td><td>${row.prediction_interval_coverage_pct == null ? "—" : `${qty(row.prediction_interval_coverage_pct,1)}%`}</td><td>${statusPill(row.status)}</td><td class="numeric">${row.selection_mae == null ? "—" : qty(row.selection_mae,2)}</td><td class="numeric">${qty(row.training_observations,0)}</td><td class="numeric">${qty(row.evaluation_observations,0)}</td><td class="numeric">${row.mae == null ? "—" : qty(row.mae,2)}</td><td class="numeric">${row.rmse == null ? "—" : qty(row.rmse,2)}</td><td class="numeric">${row.r2 == null ? "—" : qty(row.r2,3)}</td><td>${esc(reason)}${row.message ? `<br><small>${esc(row.message)}</small>` : ""}</td></tr>`;
    });
    const forecastRows = (result.forecasts[chosen] || []).map((x) => `<tr><td>${esc(x.date)}</td><td class="numeric">${qty(x.forecast,2)} ${esc(result.unit)}</td><td class="numeric">${x.lower == null || x.upper == null ? "Unavailable" : `${qty(x.lower,2)}–${qty(x.upper,2)} ${esc(result.unit)}`}</td></tr>`);
    const featureRows = (result.feature_importance || []).map((item) => `<tr><td>${esc(item.feature)}</td><td class="numeric">${qty(item.importance,4)}</td></tr>`);
    const toggles = successful.map((row) => `<label class="checkbox-row model-toggle"><input class="forecast-model-toggle" type="checkbox" value="${esc(row.model)}" ${visible.includes(row.model) ? "checked" : ""}><span>${esc(row.model)}</span></label>`).join("");
    const warningRows = result.warnings.map((x) => `<div class="alert-box info"><span class="alert-icon">i</span><span>${esc(x)}</span></div>`).join("");
    const freshness = result.freshness;
    const freshnessBox = freshness && !freshness.is_current
      ? `<div class="alert-box"><span class="alert-icon">!</span><span>Current replenishment use is disabled: the latest Dataset observation is ${esc(freshness.latest_observation_date || "unavailable")} (${freshness.age_days == null ? "age unknown" : `${freshness.age_days} days old`}); the limit is ${esc(freshness.max_age_days)} days. Charts here describe the stored holdout and periods after the source cutoff, not a current order recommendation.</span></div>`
      : `<div class="alert-box success"><span class="alert-icon">✓</span><span>Latest Dataset observation: ${esc(freshness?.latest_observation_date || "—")} · source age ${esc(freshness?.age_days ?? "—")} day(s).</span></div>`;
    return `<div id="forecast-results">
      <div class="content-grid equal">
       <section class="panel"><div class="panel-header"><div><h2 class="panel-title">Chronological model comparison</h2><p class="panel-subtitle">${badge(uiSourceLabel(result.source_label))} · ${esc(result.site)} / ${esc(result.material)} · ${esc(result.frequency)} · ${esc(result.unit)}</p></div><span class="status ${result.cache_hit ? "good" : "neutral"}">${result.cache_hit ? "Saved artifact" : "Evaluated"}</span></div><div class="score-spotlight"><div><span>Selected by rolling-origin MAE</span><strong>${esc(result.best_model)}</strong></div><div><span>Holdout MAE</span><strong>${qty(bestMetric.mae,2)} ${esc(result.unit)}</strong></div></div><div class="panel-body compact">${table(["Model","Holdout WAPE","MASE","Interval coverage","Status","Rolling MAE","Train n","Holdout n","MAE","RMSE","R²","Selection / reason"], metrics, "No model metrics", "")}</div><div class="panel-body"><div class="method-box">Selection uses mean absolute error across three expanding-window rolling origins before the final holdout. The final chronological 20% remains untouched for diagnostics. The final chronological holdout is reserved for diagnostics after rolling-origin model selection. Scores describe this dataset and are not a guarantee of future demand. ${coverageLabel({from:result.training_start,to:result.training_end})} · ${result.source_observations} source observations / ${result.calendar_periods} calendar periods.<br>Train: ${esc(bestMetric.training_start || "—")} → ${esc(bestMetric.training_end || "—")} (${qty(bestMetric.training_observations,0)} periods). Holdout: ${esc(bestMetric.test_start || result.evaluation_start || "—")} → ${esc(bestMetric.test_end || result.evaluation_end || "—")} (${qty(bestMetric.evaluation_observations,0)} scored periods). MAE/RMSE are in ${esc(result.unit)}.</div></div></section>
       <section class="panel"><div class="panel-header"><div><h2 class="panel-title">Holdout actual vs. predicted and future forecast</h2><p class="panel-subtitle">Holdout actuals and predictions are shown separately from the future forecast interval.</p></div></div><div class="panel-body compact"><div class="model-toggle-list" aria-label="Forecast model overlays">${toggles}</div></div><div class="chart-wrap"><div class="chart" id="forecast-chart"></div></div><div class="panel-body compact">${table(["Future period","Forecast","Indicative range"], forecastRows, "No forecast values", "")}</div><div class="chart-note">Chosen model: <strong>${esc(result.best_model)}</strong>. The 90% interval uses pre-holdout rolling-origin errors. Observed holdout coverage was ${result.prediction_interval?.holdout_coverage_pct == null ? "unavailable" : `${qty(result.prediction_interval.holdout_coverage_pct,1)}%`}; this is a diagnostic, not a guarantee.</div><div class="section-heading"><div><h3>Holdout residuals</h3><p>Actual minus predicted; shown for ${esc(chosen)}.</p></div></div><div class="chart-wrap"><div class="chart" id="forecast-residual-chart"></div></div></section>
      </div>
      <div class="content-grid equal" style="margin-top:13px">
       <section class="panel"><div class="panel-header"><div><h2 class="panel-title">Random Forest feature importance</h2><p class="panel-subtitle">Importance values from the fitted Random Forest artifact.</p></div></div><div class="panel-body compact">${table(["Past-only feature","Importance"], featureRows, "Feature importance unavailable", "The Random Forest artifact did not expose a compatible importance vector.")}</div></section>
       <section class="panel"><div class="panel-header"><div><h2 class="panel-title">How this works</h2><p class="panel-subtitle">One site/material series; its unit is never combined with another.</p></div></div><div class="panel-body"><div class="method-box"><strong>1. Split by time.</strong> Three expanding-window rolling origins select the model; the final 20% is held out for separate diagnostics.<br><br><strong>2. Use past-only inputs.</strong> Lag 1–4, rolling mean and rolling standard deviation are calculated strictly before each predicted period.<br><br><strong>3. Compare fairly.</strong> Naive, eligible Seasonal Naive, Multiple Linear Regression, Random Forest and XGBoost use pre-holdout rolling MAE for selection; MAE, RMSE, WAPE, MASE and interval coverage are reported on the untouched final holdout.<br><br><strong>4. Keep limitations visible.</strong> Missing periods stay missing; source coverage is displayed; a source outside the seven-day rule cannot support numeric replenishment.</div></div></section>
      </div>
      <div class="stack" style="margin-top:13px">${freshnessBox}${warningRows}</div>
    </div>`;
  }

  function forecastLeaderboardView(board = state.forecastLeaderboard) {
    const wins = [...(board?.wins || [])].sort((a,b) => b.wins-a.wins || a.model.localeCompare(b.model));
    const rows = (board?.items || []).map((item) => `<tr><td>${esc(item.site)}</td><td>${esc(item.material)}</td><td><strong>${esc(item.best_model)}</strong></td><td class="numeric">${qty(item.best_mae,2)} ${esc(item.unit)}</td><td>${esc(item.evaluation_start || "—")} → ${esc(item.evaluation_end || "—")}</td></tr>`);
    return `<section class="panel leaderboard-panel"><div class="panel-header"><div><h2 class="panel-title">Stored model leaderboard</h2><p class="panel-subtitle">Current weekly source hash · best model per site/material pair · ranked by pre-holdout rolling-origin MAE.</p></div><span class="status good">${qty(board?.pair_count || 0,0)} pairs</span></div><div class="panel-body"><div class="content-grid equal"><div>${table(["Model","Pair wins"],wins.map((x)=>`<tr><td>${esc(x.model)}</td><td class="numeric"><strong>${qty(x.wins,0)}</strong></td></tr>`),"No stored wins","Train all pairs to populate stored comparisons.")}</div><div class="method-box">Wins are calculated from saved model metrics only. Pair rankings refresh when the source hash or model version changes; no score is recomputed in this view.</div></div><div class="panel-body compact">${table(["Site","Material","Best holdout model","MAE","Evaluation window"],rows,"No current stored assessments","The training command persists one assessment per weekly site/material pair.")}</div></div></section>`;
  }

  function drawForecast(result, modelNames = null) {
    const chosen = state.forecastModel || result.best_model;
    const visible = (Array.isArray(modelNames) ? modelNames : state.forecastVisibleModels)
      .filter((name) => result.forecasts[name]);
    const colors = ["#E76D68", "#D9A441", "#41B8AA", "#76A9D1", "#C08ADB"];
    const traces = [
      { x: result.historical.map((x)=>x.date), y: result.historical.map((x)=>x.actual), type: "scatter", mode: "lines", name: "Dataset actual", line: { color: "#7d8984", width: 1.8 }, connectgaps: false },
    ];
    const holdoutActual = result.holdouts[chosen] || [];
    traces.push({ x: holdoutActual.map((x)=>x.date), y: holdoutActual.map((x)=>x.actual), type: "scatter", mode: "markers", name: "Holdout actual", marker: { color: "#F0F1EC", size: 7 }, connectgaps: false });
    visible.forEach((name, index) => {
      const color = colors[index % colors.length];
      const holdout = result.holdouts[name] || [];
      const future = result.forecasts[name] || [];
      traces.push({ x: holdout.map((x)=>x.date), y: holdout.map((x)=>x.predicted), type: "scatter", mode: "lines+markers", name: `${name} holdout`, line: { color, dash: "dash", width: 2 }, marker: { color, size: 4 }, connectgaps: false });
      traces.push({ x: future.map((x)=>x.date), y: future.map((x)=>x.forecast), type: "scatter", mode: "lines+markers", name: `${name} forecast`, line: { color, width: 2.2 }, marker: { color, size: 5 }, connectgaps: false });
    });
    plot("forecast-chart", traces, `Demand (${result.unit})`, { height: 330 });
    const residuals = (result.holdouts[chosen] || []).map((row) => ({ date: row.date, residual: Number(row.actual) - Number(row.predicted) }));
    plot("forecast-residual-chart", [{ x: residuals.map((x)=>x.date), y: residuals.map((x)=>x.residual), type: "bar", name: "Residual", marker: { color: "#E76D68" } }], `Residual (${result.unit})`, { height: 190 });
  }

  async function renderForecasting() {
    if (!catalogCheck()) return;
    const [qualityData, leaderboardData] = await Promise.all([
      api("/api/data/quality"),
      api("/api/forecasts/leaderboard"),
    ]);
    const quality = qualityData.report || {};
    state.datasetCoverage = {
      from: String(quality.date_min || "").slice(0,10),
      to: String(quality.date_max || "").slice(0,10),
      observations: quality.row_count,
    };
    state.forecastLeaderboard = leaderboardData;
    const sites = activeSites();
    const siteId = String(state.forecastSelection?.site_id || selectedSiteId());
    const materials = activeMaterials();
    const materialId = String(state.forecastSelection?.material_id || selectedMaterialId());
    const frequency = state.forecastSelection?.frequency || "weekly";
    const horizon = state.forecastSelection?.horizon_days || 30;
    const source = "historical_csv";
    state.forecastSelection = { site_id: siteId, material_id: materialId, frequency, horizon_days: horizon, source };
    const datasetSource = state.forecastResult ? uiSourceLabel(state.forecastResult.source_label) : "Dataset";
    pageView.innerHTML = `${heading("forecasting", "CHRONOLOGICAL MODEL REVIEW")}
      <div class="content-grid equal">
       <section class="form-panel"><div class="form-panel-header"><h2>Evaluation scope</h2><p>One site/material series at its recorded unit; no unit aggregation.</p></div><div class="form-panel-body"><form id="forecast-form" class="form-section">
        <div class="fields-grid">${siteSelect("forecast-site", siteId, sites)}${materialSelect("forecast-material", materialId, materials)}</div>
        <div class="fields-grid cols-3"><div class="field"><label>Frequency</label><select name="frequency"><option value="weekly" ${frequency==="weekly"?"selected":""}>Weekly</option><option value="monthly" ${frequency==="monthly"?"selected":""}>Monthly</option></select></div><div class="field"><label>Horizon (days)</label><select name="horizon_days">${(frequency==="weekly"?[7,14,30,60,90]:[30,60,90]).map((x)=>`<option value="${x}" ${Number(horizon)===x?"selected":""}>${x} days</option>`).join("")}</select></div><div class="field"><label>Forecast source</label><div class="control">Dataset observations only</div><input type="hidden" name="source" value="historical_csv"></div></div>
        <div class="alert-box info"><span class="alert-icon">i</span><span>Forecasts use this selected site/material series from the Dataset only. Coverage outside the seven-day limit cannot support a current numeric replenishment recommendation.</span></div>
        <div id="forecast-source-note" class="field-help">${esc(coverageLabel(state.datasetCoverage))} · ${qty(state.datasetCoverage?.observations,0)} source rows.</div>
        <div class="form-footer"><span class="field-help">Naive · Seasonal Naive · Multiple Linear Regression · Random Forest · XGBoost (when installed). Saved artifacts load without refitting.</span><button class="button primary" type="submit">Evaluate selected series</button></div>
       </form></div></section>
       <section class="panel"><div class="panel-header"><div><h2 class="panel-title">Evaluation protocol</h2><p class="panel-subtitle">Chronological holdout · past-only features</p></div>${badge(datasetSource)}</div><div class="panel-body"><ul class="info-list"><li>Three expanding-window rolling-origin folds select the model before the untouched final 20% chronological holdout; no random shuffle.</li><li>Lag 1–4, rolling mean and rolling standard deviation use prior values only.</li><li>MAE, RMSE, R² (when defined) and WAPE describe the final holdout; model selection uses rolling-origin MAE only.</li><li>Holdout predictions, future periods, residuals and Random Forest importance are shown.</li><li>Saved artifacts are keyed to the current data hash and model version.</li><li>Future dates are anchored after the last Dataset observation, not shifted to today.</li></ul></div></section>
      </div>
      <div id="forecast-output" style="margin-top:15px">${state.forecastResult ? forecastResultView(state.forecastResult) : emptyState("Loading saved model comparison…", "The selected default pair is evaluated as this page opens.")}</div>
      <div id="forecast-leaderboard" style="margin-top:15px">${forecastLeaderboardView(state.forecastLeaderboard)}</div>`;

    const hzSelect = $("#forecast-form select[name='horizon_days']");
    $("#forecast-form select[name='frequency']").addEventListener("change", () => {
      const freq = $("#forecast-form select[name='frequency']").value;
      hzSelect.innerHTML = (freq === "weekly" ? [7,14,30,60,90] : [30,60,90]).map((x)=>`<option value="${x}">${x} days</option>`).join("");
      hzSelect.value = "30";
      state.forecastResult = null;
      state.forecastModel = null;
      state.forecastVisibleModels = [];
    });
    $("#forecast-form").addEventListener("change", (event) => {
      state.forecastSelection = Object.fromEntries(new FormData(event.currentTarget).entries());
      state.forecastResult = null;
      state.forecastModel = null;
      state.forecastVisibleModels = [];
      const output = $("#forecast-output");
      if (output) output.innerHTML = emptyState("Evaluation settings changed", "Select Evaluate selected series to refresh holdout metrics and future periods.");
    });

    if (state.forecastResult) {
      drawForecast(state.forecastResult);
    } else {
      const form = $("#forecast-form");
      const formData = new FormData(form);
      const body = {
        site_id: Number(formData.get("site_id")),
        material_id: Number(formData.get("material_id")),
        frequency: formData.get("frequency"),
        horizon_days: Number(formData.get("horizon_days")),
        source: "historical_csv",
      };
      try {
        setBusy(true, "Loading saved model artifacts for the default pair…");
        state.forecastResult = await api("/api/forecasts/evaluate", { method: "POST", body });
        state.forecastModel = state.forecastResult.best_model;
        state.forecastVisibleModels = [state.forecastResult.best_model];
        $("#forecast-output").innerHTML = forecastResultView(state.forecastResult);
        drawForecast(state.forecastResult);
      } catch (error) {
        $("#forecast-output").innerHTML = `<div class="error-state"><strong>Model comparison unavailable</strong><br>${esc(error.message)}<br><small>Check source coverage and saved artifacts, then retry with Evaluate selected series.</small></div>`;
      } finally {
        setBusy(false);
      }
    }
  }

  async function renderReplenishment() {
    if (!catalogCheck()) return;
    const siteId = String(state.replenishmentSelection?.site_id || selectedSiteId());
    const materialId = String(state.replenishmentSelection?.material_id || selectedMaterialId());
    const query = encodeQuery({ site_id: siteId, material_id: materialId });
    const [balanceData, ruleData, alertData] = await Promise.all([
      api(`/api/inventory/balances?${query}`),
      api(`/api/reorder-rules?${query}`),
      api("/api/inventory/balances?alert_only=true"),
    ]);
    state.suppliers = (await api("/api/suppliers")).items || [];
    const balance = balanceData.items[0] || null;
    const rule = ruleData.items[0] || null;
    const alertRows = (alertData.items || []).map((item) => `<tr><td>${esc(item.site)}</td><td>${esc(item.material)}</td><td class="numeric">${qty(item.current_usable_stock)} ${esc(item.unit)}</td><td class="numeric">${qty(item.reorder_point_qty)} ${esc(item.unit)}</td><td>${statusPill(item.reorder_status)}</td></tr>`);
    const material = getMaterial(materialId);
    const leadDefault = state.replenishmentSelection?.lead_time_days ?? rule?.lead_time_days ?? material?.default_lead_time_days ?? "";
    const safetyDefault = state.replenishmentSelection?.safety_stock_days ?? rule?.safety_stock_days ?? material?.safety_stock_days ?? 7;
    const reorderPoint = rule?.reorder_point_qty ?? state.replenishmentSelection?.reorder_point_qty ?? 0;
    const result = state.replenishmentResult && String(state.replenishmentResult.site_id) === siteId && String(state.replenishmentResult.material_id) === materialId ? state.replenishmentResult : null;
    pageView.innerHTML = `${heading("replenishment", "LIVE LEDGER STOCK BASIS")}
      <div class="page-toolbar"><div class="toolbar-fields"><div class="field"><label>Project site</label><select id="repl-site">${makeOptionGroups(activeSites(),siteId,"identifier")}</select></div><div class="field"><label>Material</label><select id="repl-material">${makeOptionGroups(activeMaterials(),materialId,"name")}</select></div><div class="field"><label>Live ledger stock</label><div class="control">${balance?.current_usable_stock == null ? "Not initialized" : `${qty(balance.current_usable_stock)} ${esc(material?.unit || "")}`}</div></div><div class="field"><label>Reorder status</label><div class="control">${balance ? statusPill(balance.reorder_status) : "—"}</div></div></div></div>
      ${balance?.current_usable_stock == null ? `<div class="alert-box"><span class="alert-icon">!</span><span>No opening count exists for this pair. Record a verified physical count in Inventory; no historical stock value is used as current stock.</span></div>` : ""}
      <div class="content-grid equal" style="margin-top:13px">
       <section class="form-panel"><div class="form-panel-header"><h2>Site/material reorder rule</h2><p>Threshold alerts and planning overrides are stored per pair; units follow the material catalogue.</p></div><div class="form-panel-body"><form id="reorder-rule-form" class="form-section"><input type="hidden" name="site_id" value="${esc(siteId)}"><input type="hidden" name="material_id" value="${esc(materialId)}"><input type="hidden" name="unit" value="${esc(material?.unit || "")}">
        <div class="fields-grid cols-3"><div class="field"><label>Reorder point (${esc(material?.unit || "unit")})</label><input name="reorder_point_qty" type="number" min="0" step="0.0001" value="${esc(reorderPoint)}" required></div><div class="field"><label>Lead time (days)</label><input name="lead_time_days" type="number" min="1" max="365" value="${esc(rule?.lead_time_days ?? material?.default_lead_time_days ?? "")}" placeholder="Required for planning"></div><div class="field"><label>Legacy safety days (not used by risk)</label><input name="safety_stock_days" type="number" min="0" max="90" value="${esc(rule?.safety_stock_days ?? material?.safety_stock_days ?? 7)}"></div><div class="field"><label>Minimum order qty</label><input name="minimum_order_qty" type="number" min="0" step="0.0001" value="${esc(rule?.minimum_order_qty ?? material?.minimum_order_qty ?? 0)}"></div><div class="field"><label>Order multiple</label><input name="order_multiple" type="number" min="0" step="0.0001" value="${esc(rule?.order_multiple ?? material?.order_multiple ?? 0)}"></div><div class="field"><label>Maximum stock qty</label><input name="maximum_stock_qty" type="number" min="0" step="0.0001" value="${esc(rule?.maximum_stock_qty ?? material?.maximum_stock_qty ?? "")}"></div></div>
        <div class="field"><label>Rule note (optional)</label><input name="notes" value="${esc(rule?.notes || "")}" placeholder="Local policy / rationale"></div><div class="form-footer"><span class="field-help">Below-point alert uses live ledger balance only.</span><button class="button" type="submit">Save reorder rule</button></div>
       </form></div></section>
       <section class="form-panel"><div class="form-panel-header"><h2>Calculate replenishment</h2><p>Coverage beyond seven days, missing physical stock or unsupported lead time withholds the numeric recommendation.</p></div><div class="form-panel-body"><form id="replenishment-form" class="form-section">
        <div class="fields-grid cols-3"><div class="field"><label>Lead time (days)</label><input name="lead_time_days" type="number" min="1" max="365" value="${esc(leadDefault)}" placeholder="Enter lead time" required></div><div class="field"><label>Target service level</label><select name="service_level"><option value="0.9">90%</option><option value="0.95" selected>95%</option><option value="0.98">98%</option></select><small>Sets the z score for safety stock.</small></div><div class="field"><label>Demand source</label><div class="control">Dataset observations only</div><input type="hidden" name="source" value="historical_csv"></div></div>
        <div class="fields-grid cols-3"><div class="field"><label>Confirmed incoming qty (scenario only)</label><input name="incoming_quantity" type="number" min="0" step="0.0001" value="" placeholder="Optional"></div><div class="field"><label>Expected date</label><input name="incoming_date" type="date" min="${todayString}" max="${localDateString(new Date(Date.now()+365*86400000))}"></div><div class="field"><label>Confirmation reference</label><input name="incoming_reference" maxlength="120" placeholder="Optional"></div></div>
        <div class="alert-box info"><span class="alert-icon">i</span><span>The demand source is the Dataset only. Incoming quantity is a one-time user-confirmed scenario; it does not create a delivery, receipt or ledger transaction. Current numeric advice is withheld when source coverage is outside the seven-day limit.</span></div>
        <div class="form-footer"><span class="field-help">Weekly forecasts are not extrapolated beyond 90 days.</span><button class="button primary" type="submit">Calculate recommendation</button></div>
       </form></div></section>
      </div>
      <div class="section-heading"><div><h2>Calculation result</h2><p>Live balance is the stock basis. Historical stock figures are never substituted.</p></div></div>
      <div id="replenishment-output">${result ? replenishmentResultView(result) : emptyState("No calculation run yet", "Save or confirm a site/material rule, then calculate a recommendation.")}</div>
      <div class="section-heading"><div><h2>All pairs below reorder point</h2><p>Calculated from initialized live ledger balances and active rules.</p></div></div>
      ${table(["Site","Material","Live stock","Reorder point","Risk"],alertRows,"No pairs are currently below their reorder point","No current stock alerts are computed without both a physical count and an active rule.")}
      <div class="section-heading"><div><h2>Transparent calculation</h2><p>Reserve, lead-time demand and constraints are reported separately.</p></div></div>
      <div class="formula-box"><strong>Lead-time demand</strong> = weekly forecast × lead weeks. <strong>Safety stock</strong> = z(service level) × forecast-error sigma × √lead weeks.<br>Risk precedence is High → Medium → Low; overstock is an independent flag. Order quantity is the greater of order-up-to gap, EOQ and minimum quantity, rounded to pack size. Maximum-stock conflicts are flagged. Reference-price estimates are not audited spend.</div>`;
    state.replenishmentSelection = { site_id: siteId, material_id: materialId, lead_time_days: leadDefault, safety_stock_days: safetyDefault, reorder_point_qty: reorderPoint };
    $("#repl-site").addEventListener("change", (event) => { state.siteId = event.target.value; state.replenishmentSelection = null; state.replenishmentResult = null; renderPage(); });
    $("#repl-material").addEventListener("change", (event) => { state.materialId = event.target.value; state.replenishmentSelection = null; state.replenishmentResult = null; renderPage(); });
    if (result?.recommendation?.recommended_order_qty > 0 && !result.recommendation.capacity_conflict) {
      const supplierOptions = opt(state.suppliers, "id", (x) => x.name, "", "Select supplier");
      $("#replenishment-output").insertAdjacentHTML("beforeend", `<section class="form-panel" style="margin-top:12px"><div class="form-panel-header"><h2>Create purchase order</h2><p>Uses the displayed recommendation quantity and material unit. The order starts as Draft.</p></div><div class="form-panel-body"><div class="fields-grid cols-3"><div class="field"><label>Supplier</label><select id="recommendation-supplier">${supplierOptions}</select></div><div class="field"><label>Unit price (INR / ${esc(result.unit)})</label><input id="recommendation-price" type="number" min="0" step="0.01" value="${esc(result.recommendation.unit_price ?? 0)}"></div><div class="field"><label>Expected delivery</label><input id="recommendation-date" type="date" min="${todayString}"></div></div><button class="button primary" data-action="create-po-from-recommendation" data-site="${esc(siteId)}" data-material="${esc(materialId)}">Create PO for ${qty(result.recommendation.recommended_order_qty)} ${esc(result.unit)}</button></div></section>`);
    }
  }

  async function renderPurchasing() {
    const [supplierData, poData] = await Promise.all([api("/api/suppliers"), api("/api/purchase-orders")]);
    state.suppliers = supplierData.items || [];
    const rows = (poData.items || []).map((po) => `<tr><td>${esc(po.po_number)}</td><td>${esc(po.supplier)}</td><td>${esc(po.site)}</td><td>${statusPill(po.status)}</td><td>${(po.lines || []).map((line) => `${esc(line.material)}: ${qty(line.quantity_received)}/${qty(line.quantity_ordered)} ${esc(line.unit)}${line.outstanding > 0 ? ` <button class="button small" data-action="receive-po-line" data-line="${line.id}" data-outstanding="${line.outstanding}" data-unit="${esc(line.unit)}">Receive remaining</button>` : ""}`).join("<br>")}</td><td>${po.status === "Draft" ? `<button class="button small" data-action="po-approve" data-id="${po.id}" data-status="Pending approval">Submit</button>` : ""}${po.status === "Pending approval" ? `<button class="button small" data-action="po-approve" data-id="${po.id}" data-status="Approved">Approve</button>` : ""}</td></tr>`);
    pageView.innerHTML = `${heading("purchasing", "SUPPLIERS + PURCHASE ORDERS")}<section class="form-panel"><div class="form-panel-header"><h2>Add supplier</h2><p>Supplier contact details are optional; supplier names must be unique.</p></div><div class="form-panel-body"><form id="supplier-form" class="fields-grid cols-3"><div class="field"><label>Name</label><input name="name" required maxlength="160"></div><div class="field"><label>Email (optional)</label><input name="email" type="email"></div><div class="field"><label>Phone (optional)</label><input name="phone"></div><button class="button primary" type="submit">Add supplier</button></form><p class="field-help">Active suppliers: ${state.suppliers.map((x) => esc(x.name)).join(", ") || "None configured"}</p></div></section><div class="section-heading"><div><h2>Purchase orders</h2><p>Receipts are posted to the stock ledger and update the PO status.</p></div></div>${table(["PO","Supplier","Site","Status","Lines / receipts","Action"], rows, "No purchase orders", "Calculate replenishment and create an order, or configure a supplier.")}`;
  }

  function replenishmentResultView(result) {
    const rec = result.recommendation;
    const sourceAge = result.source_freshness?.age_days;
    const sourceIsStale = result.status === "stale_demand_source" || (sourceAge != null && Number(sourceAge) > 7);
    const sourceBanner = sourceIsStale
      ? `<div class="alert-box"><span class="alert-icon">!</span><span>${badge(uiSourceLabel(result.source_label),result.source_label === "Operational sales")} ${result.source_freshness?.latest_observation_date ? `Latest source date ${esc(result.source_freshness.latest_observation_date)} (${esc(sourceAge)} days old); current recommendation is withheld.` : "The selected demand source is outside the seven-day freshness window."}</span></div>`
      : "";
    if (!rec) {
      const warnings = (result.warnings || []).map((w) => `<div class="alert-box"><span class="alert-icon">!</span><span>${esc(w)}</span></div>`).join("");
      return `<div class="stack">${sourceBanner}<div class="panel"><div class="panel-body"><div class="kpi-grid">${card("Current stock", result.current_stock === null ? "Not initialized" : `${qty(result.current_stock)} ${esc(result.unit)}`, "Operational ledger", "teal-top", true)}${card("Lead time", result.lead_time_days ? `${result.lead_time_days} days` : "Required", "Configured / entered assumption")}${card("Inventory risk", result.risk?.risk_level || "High", `Service level ${qty((result.risk?.service_level || 0.95) * 100,0)}%`)}${card("Recommendation", "Withheld", esc(statusLabel(result.status)), "red-top", true)}</div>${warnings}</div></div></div>`;
    }
    const warnings = [...(result.warnings || []), ...(result.daily_rate_warnings || [])].map((w) => `<div class="alert-box info"><span class="alert-icon">i</span><span>${esc(w)}</span></div>`).join("");
    const stepRows = [
      ["1 · Current usable stock (live ledger)", rec.current_stock == null ? "Unknown — physical count required" : `${qty(rec.current_stock)} ${result.unit}`],
      ["2 · Selected forecast", `${(rec.forecast_values || []).map((v) => qty(v)).join(", ") || "No forecast values; historical-rate fallback"} ${result.unit} per ${rec.forecast_step_days || 7} days`],
      ["3 · Lead time", `${rec.lead_time_days} days · ${rec.demand_basis}`],
      ["4 · Forecast demand over lead time", `${qty(rec.lead_time_demand)} ${result.unit}`],
      ["5 · Service level and safety reserve", `${qty((rec.risk?.service_level || 0.95) * 100,0)}% service · z=${qty(rec.risk?.z_score,3)} → ${qty(rec.safety_stock_qty)} ${result.unit}`],
      ["6 · Eligible incoming by lead-time date", `${qty(rec.eligible_incoming_qty)} ${result.unit}`],
      ["7 · Net requirement before order rules", rec.net_requirement_before_constraints == null ? "Unavailable" : `max(0, ${qty(rec.lead_time_demand)} + ${qty(rec.safety_stock_qty)} − ${qty(rec.current_stock)} − ${qty(rec.eligible_incoming_qty)}) = ${qty(rec.net_requirement_before_constraints)} ${result.unit}`],
      ["8 · Minimum order / multiple applied", `${qty(rec.minimum_order_qty)} / ${qty(rec.order_multiple)} ${result.unit}`],
      ["9 · Final recommendation", rec.recommended_order_qty == null ? "Unavailable" : `${qty(rec.recommended_order_qty)} ${result.unit} · ${result.status}`],
      ["10 · Cost estimate and risk", `${rec.estimated_order_cost_inr == null ? "Cost unavailable" : money(rec.estimated_order_cost_inr)} · ${result.status}`],
      ["11 · Suggested action", `${rec.risk?.suggestion?.action || "Review"} · ${rec.risk?.suggestion?.reason || "See warnings"} · order by ${rec.risk?.suggestion?.order_by_date || "—"}`],
    ].map(([step, value]) => `<tr><td>${esc(step)}</td><td><strong>${esc(value)}</strong></td></tr>`);
    return `<div class="stack">${sourceBanner}<div class="panel"><div class="panel-header"><div><h2 class="panel-title">${esc(result.site)} / ${esc(result.material)}</h2><p class="panel-subtitle">${esc(result.unit)} · ${esc(result.model_name || "No model")}</p></div>${statusPill(result.status)}</div><div class="panel-body"><div class="kpi-grid">${card("Lead-time demand", `${qty(rec.lead_time_demand)} ${esc(result.unit)}`, `${result.lead_time_days} days`, "blue-top", true)}${card("Safety stock", `${qty(rec.safety_stock_qty)} ${esc(result.unit)}`, `${qty((rec.risk?.service_level || 0.95) * 100,0)}% service`, "")}${card("Eligible incoming", `${qty(rec.eligible_incoming_qty)} ${esc(result.unit)}`, "Approved PO pipeline + confirmed scenario")}${card("Recommended order", rec.recommended_order_qty == null ? "Unavailable" : `${qty(rec.recommended_order_qty)} ${esc(result.unit)}`, esc(rec.status), rec.capacity_conflict ? "red-top" : "teal-top", true)}</div><div class="section-heading"><div><h3>Why this number</h3><p>Calculation inputs and each arithmetic step for this recommendation.</p></div></div><div class="panel-body compact">${table(["Calculation step","Value"],stepRows,"No calculation steps","The source or stock checks withheld a numeric result.")}</div><div class="content-grid equal"><div class="method-box">Live ledger stock: <strong>${qty(rec.current_stock)} ${esc(result.unit)}</strong><br>Stock basis: ${esc(rec.current_stock_basis)}<br>Historical daily rate: ${result.historical_daily_rate == null ? "Unavailable" : `${qty(result.historical_daily_rate,4)} ${esc(result.unit)}/day`}<br>Forecast source: <strong>${esc(uiSourceLabel(result.source_label))}</strong><br>Forecast model: ${esc(result.model_name || "—")}</div><div class="method-box">Net requirement before constraints: <strong>${qty(rec.net_requirement_before_constraints)} ${esc(result.unit)}</strong><br>Minimum order: ${qty(rec.minimum_order_qty)} ${esc(result.unit)}<br>Order multiple: ${qty(rec.order_multiple)} ${esc(result.unit)}<br>Expected arrival: ${esc(rec.expected_arrival_date || "—")}<br>Cost estimate: ${rec.estimated_order_cost_inr == null ? "Unavailable" : money(rec.estimated_order_cost_inr)} <span class="muted">(${esc(rec.price_basis || "no price basis")})</span></div></div>${rec.capacity_conflict ? `<div class="alert-box error"><span class="alert-icon">!</span><span>Maximum-stock conflict: the required quantity exceeds configured capacity. Resolve it before action.</span></div>` : ""}${warnings}</div></div></div>`;
  }
  function statusLabel(status) {
    const map = { needs_physical_count: "Needs count", stale_demand_source: "Source outside current window", lead_time_required: "Need lead time", lead_time_exceeds_forecast_horizon: "Horizon exceeded", demand_rate_unavailable: "Rate unavailable" };
    return map[status] || status;
  }

  async function renderReports() {
    const [qualityData, imports] = await Promise.all([api("/api/data/quality"), api("/api/data/imports")]);
    const r = qualityData.report || {};
    const warnings = (r.warnings || []).map((x) => `<div class="alert-box info"><span class="alert-icon">i</span><span>${esc(x)}</span></div>`).join("");
    const missing = Object.entries(r.missing_by_column || {}).filter(([,v])=>Number(v)>0).map(([k,v])=>`${k}: ${v}`).join(" · ") || "None reported";
    const runRows = (imports.items || []).map((x) => `<tr><td>${x.id}</td><td>${esc(x.file_name)}</td><td>${statusPill(x.status)}</td><td class="numeric">${x.total_rows}</td><td class="numeric">${x.accepted_rows}</td><td class="numeric">${x.rejected_rows}</td><td class="numeric">${x.duplicate_rows}</td><td>${esc(x.imported_at)}</td></tr>`);
    const rejectedRows = (imports.rejected_rows || []).slice(0,60).map((x) => `<tr><td>${x.import_id}</td><td>${esc(x.file_name)}</td><td>${x.row_number}</td><td>${esc(x.reason)}</td><td><details><summary>View raw row</summary><pre class="code-preview">${esc(x.raw_json)}</pre></details></td></tr>`);
    const validation = state.data.validation;
    const uploadState = validation ? `<div class="stack" style="margin-top:14px"><div class="alert-box ${validation.schema_errors?.length ? "error" : "success"}"><span class="alert-icon">${validation.schema_errors?.length ? "!" : "✓"}</span><span>${esc(validation.file_name)} · ${validation.total_rows} rows · ${validation.accepted_rows} valid · ${validation.rejected_rows} rejected${validation.already_imported ? " · this file hash has already been imported" : ""}${validation.schema_errors?.length ? `<br>Schema: ${esc(validation.schema_errors.join("; "))}` : ""}</span></div>${validation.valid_preview?.length ? `<div><div class="section-heading"><div><h2>Normalized preview</h2><p>First 20 valid rows</p></div></div>${table((validation.columns || []).slice(0,8),validation.valid_preview.slice(0,12).map((x)=>`<tr>${(validation.columns||[]).slice(0,8).map((c)=>`<td>${esc(x[c])}</td>`).join("")}</tr>`),"No valid rows","")}</div>` : ""}${validation.rejected_preview?.length ? `<div><div class="section-heading"><div><h2>Rows with issues</h2><p>Invalid rows are retained in the import audit after confirmation.</p></div></div>${table(["CSV row","Reason","Original source row"],validation.rejected_preview.slice(0,25).map((x)=>`<tr><td>${x.row_number}</td><td>${esc(x.reason)}</td><td><details><summary>View</summary><pre class="code-preview">${esc(JSON.stringify(x.raw,null,2))}</pre></details></td></tr>`),"No invalid rows","")}</div>` : ""}<div class="form-footer"><label class="checkbox-row"><input type="checkbox" id="confirm-import" ${validation.already_imported || validation.schema_errors?.length ? "disabled" : ""}> I reviewed the normalized rows and validation outcomes.</label><button class="button primary" data-action="import-upload" ${validation.already_imported || validation.schema_errors?.length ? "disabled" : ""}>Confirm historical import</button></div></div>` : "";
    const data = state.data.importResult;
    pageView.innerHTML = `${heading("reports", "SOURCE AUDIT + OPERATIONAL REPORTING")}
      <div class="muted" style="margin:-6px 0 14px;font-size:12px">Data source: rows after 2025-12-29 and all operational records are sample data</div>
      <div class="kpi-grid">${card("Dataset observations", qty(r.row_count,0), "Imported source rows only")}${card("Sites / materials", `${r.site_count || 0} / ${r.material_count || 0}`, "Source catalogue coverage", "teal-top")}${card("Coverage", r.date_min ? `${esc(String(r.date_min).slice(0,10))} → ${esc(String(r.date_max).slice(0,10))}` : "No dates", "Observed calendar dates", "blue-top coverage-card", true)}${card("Rejected source rows", qty(qualityData.rejected_row_count || 0,0), "Invalid rows remain auditable", (qualityData.rejected_row_count||0) ? "red-top" : "")}</div>
      <div class="content-grid equal"><section class="panel"><div class="panel-header"><div><h2 class="panel-title">Dataset source quality</h2><p class="panel-subtitle">Imported observation records · operational rows are excluded.</p></div>${badge("Dataset")}</div><div class="panel-body"><div class="fields-grid cols-3"><div class="method-box"><span class="callout-title">Units</span><br>${Object.entries(r.unit_distribution||{}).map(([k,v])=>`${esc(k)}: ${v}`).join("<br>") || "—"}</div><div class="method-box"><span class="callout-title">Observation cadence</span><br>${r.median_observation_interval_days ? `${qty(r.median_observation_interval_days,2)} day median` : "—"}<br>${r.series_count || 0} site/material series</div><div class="method-box"><span class="callout-title">Missing values</span><br>${esc(missing)}</div></div><div class="section-rule"></div><div class="method-box">${r.stock_rollforward_consistency_pct != null ? `Historical adjacent stock-flow checks: ${r.stock_rollforward_pairs_within_0_01}/${r.stock_rollforward_comparable_pairs} pairs within 0.01 (${qty(r.stock_rollforward_consistency_pct,1)}%).` : "No stock-flow comparison available."}<br><br><strong>Interpretation:</strong> historical opening/incoming/consumption fields do not initialize current stock. <code>wpi_reference_month</code> is a month key only, not an index value.</div></div></section>
       <section class="panel"><div class="panel-header"><div><h2 class="panel-title">CSV validation &amp; import</h2><p class="panel-subtitle">Preview first, confirm explicitly; never creates operational transactions.</p></div><span class="status neutral">Historical only</span></div><div class="panel-body"><div class="file-drop"><strong>Select a compatible construction CSV</strong><span>Required schema is validated; upload limit 25 MB.</span><input type="file" id="csv-file" accept=".csv,text/csv"></div><div class="button-row" style="margin-top:11px"><button class="button" data-action="validate-upload">Validate &amp; preview</button><span class="field-help">${state.data.uploadFile ? esc(state.data.uploadFile.name) : "No file selected"}</span></div>${uploadState}${data ? `<div class="alert-box success" style="margin-top:12px"><span class="alert-icon">✓</span><span>Import ${data.run_id}: ${data.accepted_rows} accepted, ${data.rejected_rows} rejected, ${data.duplicate_rows} duplicate(s)${data.duplicate_file ? " · identical file already imported" : ""}. No stock or sales transactions were created.</span></div>` : ""}</div></section></div>
      ${warnings}
      <div class="section-heading"><div><h2>Import history</h2><p>SHA-256 idempotency and row-level rejection audit.</p></div></div>
      ${table(["Run","File","Status","Total","Accepted","Rejected","Duplicates","Imported at"],runRows,"No CSV import runs","Construction Materials Dehradun Dataset is imported once at first launch.")}
      <div class="section-heading"><div><h2>Rejected rows audit</h2><p>Original source row JSON and reason are preserved for review.</p></div></div>
      ${table(["Import","File","Row","Reason","Source row"],rejectedRows,"No rejected rows","Invalid rows are not silently discarded.")}
      <div class="section-heading"><div><h2>Exports</h2><p>Historical and operational datasets stay separate in each download.</p></div></div>
      <div class="panel"><div class="panel-body"><div class="button-row"><a class="button" href="/api/reports/current-inventory.csv" download>Current balances CSV</a><a class="button" href="/api/reports/ledger.csv" download>Operational ledger CSV</a><a class="button" href="/api/reports/sales.csv" download>Operational sales CSV</a><a class="button" href="/api/reports/historical.csv" download>Historical observations CSV</a><a class="button" href="/api/reports/quality.csv" download>Quality summary CSV</a><a class="button" href="/api/forecasts/metadata" target="_blank" rel="noopener">Forecast metadata JSON</a><a class="button primary" href="/api/reports/workbook.xlsx" download>Reports workbook XLSX</a></div><p class="panel-subtitle" style="margin-top:12px">CSV exports are UTF-8 with a BOM for spreadsheet compatibility. Stock value and gross margin remain blank when the recorded cost basis is incomplete.</p></div></div>
      <div class="section-heading"><div><h2>Forecast source policy</h2><p>The model view uses only the imported Dataset.</p></div></div><div class="method-box">Forecasts are trained per site/material from this Dataset. Operational sales remain a separate source for revenue and margin reporting and are not included in the model inputs. Date coverage is shown above; missing periods remain missing, not zero.</div>`;
  }

  function bindUnitFromMaterial(form) {
    if (!form) return;
    const select = form.querySelector('select[name="material_id"]');
    const material = getMaterial(select?.value || selectedMaterialId());
    const unitInput = form.querySelector('input[name="unit"]') || form.querySelector('input[name="unit_display"]') || form.querySelector("#txn-unit");
    if (unitInput && material) unitInput.value = material.unit;
    const label = form.querySelector('label[for="txn-quantity"]');
    if (label && material) label.textContent = `Quantity (${material.unit})`;
    select?.addEventListener("change", () => {
      const selected = getMaterial(select.value);
      if (unitInput && selected) unitInput.value = selected.unit;
      if (label && selected) label.textContent = `Quantity (${selected.unit})`;
    });
  }
  function updateTransactionFields() {
    const form = $("#transaction-form");
    if (!form) return;
    const kind = form.querySelector('[name="transaction_type"]').value;
    form.querySelectorAll(".adjustment-field").forEach((el) => el.classList.toggle("hidden", kind !== "adjustment"));
    const qtyInput = form.querySelector('[name="quantity"]');
    if (kind === "adjustment") { qtyInput.min = "-999999999"; qtyInput.step = "0.0001"; qtyInput.placeholder = "Signed quantity; non-zero"; }
    else { qtyInput.min = "0.0001"; qtyInput.placeholder = "Enter quantity"; }
    const cost = form.querySelector(".cost-field");
    if (cost) cost.classList.toggle("hidden", kind === "consumption");
  }
  function fillAdminForms() {
    const all = state.catalogAll;
    if (!all) return;
    const siteSelectEl = $("#site-admin-select");
    if (siteSelectEl) siteSelectEl.addEventListener("change", () => { state.adminSiteId = siteSelectEl.value; renderPage(); });
    const materialSelectEl = $("#material-admin-select");
    if (materialSelectEl) materialSelectEl.addEventListener("change", () => { state.adminMaterialId = materialSelectEl.value; renderPage(); });
  }

  async function renderPage() {
    setBusy(true, "Loading local records…");
    pageLoading();
    try {
      if (state.page !== "reports") await loadCatalog(false);
      switch (state.page) {
        case "dashboard": await renderDashboard(); break;
        case "inventory": await renderInventory(); break;
        case "sales": await renderSales(); break;
        case "forecasting": await renderForecasting(); break;
        case "replenishment": await renderReplenishment(); break;
        case "purchasing": await renderPurchasing(); break;
        case "reports": await renderReports(); break;
        default: state.page = "dashboard"; await renderDashboard();
      }
    } catch (error) {
      pageView.innerHTML = `${heading(state.page)}<div class="error-state"><strong>Unable to load ${esc(PAGE_META[state.page]?.title || "page")}</strong><br>${esc(error.message || "Unexpected error")}</div><div style="margin-top:12px"><button class="button" data-action="retry-page">Retry</button></div>`;
    } finally {
      setBusy(false);
      $$(".nav-item").forEach((button) => button.classList.toggle("active", button.dataset.page === state.page));
      $("#crumb-page").textContent = PAGE_META[state.page]?.crumb || "DASHBOARD";
    }
  }

  async function submitTransaction(form) {
    const fd = new FormData(form);
    const type = fd.get("transaction_type");
    const material = getMaterial(fd.get("material_id"));
    const body = {
      idempotency_key: fd.get("idempotency_key"),
      site_id: Number(fd.get("site_id")),
      material_id: Number(fd.get("material_id")),
      transaction_type: type,
      quantity: Number(fd.get("quantity")),
      unit: material?.unit || "",
      transaction_date: fd.get("transaction_date"),
      reference: fd.get("reference") || null,
      notes: fd.get("notes") || null,
      reason: type === "adjustment" ? fd.get("reason") : null,
      unit_cost_inr: type !== "consumption" && fd.get("unit_cost_inr") !== "" ? Number(fd.get("unit_cost_inr")) : null,
    };
    await api("/api/inventory/transactions", { method: "POST", body });
    toast(`${type.replaceAll("_"," ")} movement posted to the operational ledger.`);
    state.siteId = body.site_id; state.materialId = body.material_id;
    await renderPage();
  }
  async function submitSale(form) {
    const fd = new FormData(form);
    const material = getMaterial(fd.get("material_id"));
    const body = {
      idempotency_key: fd.get("idempotency_key"),
      site_id: Number(fd.get("site_id")),
      material_id: Number(fd.get("material_id")),
      customer_id: fd.get("customer_id") ? Number(fd.get("customer_id")) : null,
      quantity: Number(fd.get("quantity")),
      unit: material?.unit || "",
      unit_sale_price_inr: Number(fd.get("unit_sale_price_inr")),
      sale_date: fd.get("sale_date"),
      reference: fd.get("reference") || null,
      notes: fd.get("notes") || null,
    };
    const result = await api("/api/sales", { method: "POST", body });
    toast(result.item.gross_margin_inr === null ? `Sale recorded · revenue ${money(result.item.revenue_inr)} · margin unavailable without fully recorded cost.` : `Sale recorded · margin ${money(result.item.gross_margin_inr)}.`);
    state.siteId = body.site_id; state.materialId = body.material_id;
    await renderPage();
  }
  async function submitCustomer(form) {
    const fd = new FormData(form);
    const body = Object.fromEntries(fd.entries());
    const result = await api("/api/customers", { method: "POST", body });
    toast(`Customer “${result.item.name}” added.`);
    await loadCatalog(false);
    await renderPage();
  }
  async function submitInventoryFilter(form) {
    const fd = new FormData(form);
    state.inventoryFilters = { ...state.inventoryFilters, ...Object.fromEntries(fd.entries()), page: 1 };
    await renderPage();
  }
  async function submitSalesFilter(form) {
    const fd = new FormData(form);
    state.salesFilters = { ...state.salesFilters, ...Object.fromEntries(fd.entries()), page: 1 };
    await renderPage();
  }
  async function submitDashboardFilter(form) {
    const fd = new FormData(form);
    state.dashboardFilters = Object.fromEntries(fd.entries());
    state.siteId = state.dashboardFilters.site_id;
    state.materialId = state.dashboardFilters.material_id;
    await renderPage();
  }
  async function submitForecast(form) {
    const fd = new FormData(form);
    const body = {
      site_id: Number(fd.get("site_id")),
      material_id: Number(fd.get("material_id")),
      frequency: fd.get("frequency"),
      horizon_days: Number(fd.get("horizon_days")),
      source: fd.get("source"),
    };
    state.forecastSelection = { ...body };
    state.forecastResult = null;
    state.forecastModel = null;
    state.forecastVisibleModels = [];
    setBusy(true, "Evaluating chronological models…");
    try {
      const result = await api("/api/forecasts/evaluate", { method: "POST", body });
      state.forecastResult = result;
      state.forecastModel = result.best_model;
      state.forecastVisibleModels = [result.best_model];
      toast(`Model comparison ready · source: ${uiSourceLabel(result.source_label)} · pre-holdout rolling MAE: ${qty(result.metrics.find((x)=>x.model===result.best_model)?.selection_mae,2)} ${result.unit}.`, "success");
      await renderPage();
    } catch (error) {
      setBusy(false);
      showError(error.message, $("#forecast-output") || pageView);
    }
  }
  async function submitReorderRule(form) {
    const fd = new FormData(form);
    const siteId = Number(fd.get("site_id"));
    const materialId = Number(fd.get("material_id"));
    const body = {
      site_id: siteId, material_id: materialId, unit: fd.get("unit"),
      reorder_point_qty: Number(fd.get("reorder_point_qty")),
      lead_time_days: fd.get("lead_time_days") ? Number(fd.get("lead_time_days")) : null,
      safety_stock_days: fd.get("safety_stock_days") !== "" ? Number(fd.get("safety_stock_days")) : null,
      minimum_order_qty: fd.get("minimum_order_qty") !== "" ? Number(fd.get("minimum_order_qty")) : null,
      order_multiple: fd.get("order_multiple") !== "" ? Number(fd.get("order_multiple")) : null,
      maximum_stock_qty: fd.get("maximum_stock_qty") !== "" ? Number(fd.get("maximum_stock_qty")) : null,
      is_active: true, notes: fd.get("notes") || null,
    };
    await api(`/api/reorder-rules/${siteId}/${materialId}`, { method: "PUT", body });
    toast("Site/material reorder rule saved.");
    state.replenishmentResult = null;
    await renderPage();
  }
  async function submitReplenishment(form) {
    const fd = new FormData(form);
    const selection = state.replenishmentSelection || { site_id: selectedSiteId(), material_id: selectedMaterialId() };
    const body = {
      site_id: Number(selection.site_id), material_id: Number(selection.material_id),
      lead_time_days: Number(fd.get("lead_time_days")),
      service_level: Number(fd.get("service_level")),
      source: fd.get("source"),
      incoming_quantity: fd.get("incoming_quantity") ? Number(fd.get("incoming_quantity")) : null,
      incoming_date: fd.get("incoming_date") || null,
      incoming_reference: fd.get("incoming_reference") || null,
    };
    setBusy(true, "Checking source, live stock and reorder assumptions…");
    try {
      const result = await api("/api/replenishment/calculate", { method: "POST", body });
      result.site_id = body.site_id; result.material_id = body.material_id;
      state.replenishmentResult = result;
      toast(result.recommendation ? `Recommendation calculated from ${result.source_label}.` : `Planner status: ${statusLabel(result.status)}.`, result.recommendation ? "success" : "info");
      await renderPage();
    } catch (error) {
      setBusy(false);
      showError(error.message, $("#replenishment-output") || pageView);
    }
  }
  async function createSite(form) {
    const body = Object.fromEntries(new FormData(form).entries());
    await api("/api/sites", { method: "POST", body });
    toast("Project site added.");
    await loadCatalog(true); await loadCatalog(false); await renderPage();
  }
  async function updateSite(form) {
    const fd = new FormData(form); const siteId = fd.get("site_id");
    const body = { name: fd.get("name"), city: fd.get("city"), state: fd.get("state"), project_type: fd.get("project_type") || null };
    await api(`/api/sites/${siteId}`, { method: "PATCH", body });
    toast("Project site details saved."); await loadCatalog(true); await loadCatalog(false); await renderPage();
  }
  async function createMaterial(form) {
    const body = Object.fromEntries(new FormData(form).entries());
    body.safety_stock_days = 7; body.minimum_order_qty = 0; body.order_multiple = 0;
    await api("/api/materials", { method: "POST", body });
    toast("Material added."); await loadCatalog(true); await loadCatalog(false); await renderPage();
  }
  async function updateMaterial(form) {
    const fd = new FormData(form); const materialId = fd.get("material_id");
    const number = (key) => fd.get(key) === "" ? null : Number(fd.get(key));
    const body = {
      name: fd.get("name"), unit: fd.get("unit"),
      default_lead_time_days: number("default_lead_time_days"),
      safety_stock_days: number("safety_stock_days"),
      minimum_order_qty: number("minimum_order_qty") ?? 0,
      order_multiple: number("order_multiple") ?? 0,
      maximum_stock_qty: number("maximum_stock_qty"),
      benchmark_unit_price_inr: number("benchmark_unit_price_inr"),
      is_active: fd.get("is_active") === "on",
    };
    await api(`/api/materials/${materialId}`, { method: "PATCH", body });
    toast("Material details saved."); await loadCatalog(true); await loadCatalog(false); await renderPage();
  }
  async function toggleCatalogue(kind, id, current) {
    const url = kind === "site" ? `/api/sites/${id}` : `/api/materials/${id}`;
    await api(url, { method: "PATCH", body: { is_active: current !== "true" } });
    toast(`${kind === "site" ? "Site" : "Material"} ${current === "true" ? "deactivated" : "activated"}.`, "info");
    await loadCatalog(true); await loadCatalog(false); await renderPage();
  }
  async function validateUpload() {
    const input = $("#csv-file");
    if (input?.files?.[0]) state.data.uploadFile = input.files[0];
    if (!state.data.uploadFile) { toast("Choose a CSV file to validate.", "error"); return; }
    const form = new FormData(); form.append("file", state.data.uploadFile);
    setBusy(true, "Validating CSV without importing it…");
    try {
      state.data.validation = await api("/api/data/validate", { method: "POST", body: form });
      state.data.importResult = null;
      await renderPage();
      toast(`Validation complete · ${state.data.validation.accepted_rows} valid · ${state.data.validation.rejected_rows} with issues.`, "info");
    } catch (error) { setBusy(false); showError(error.message); }
  }
  async function importUpload() {
    if (!state.data.uploadFile || !state.data.validation) { toast("Validate a CSV before importing.", "error"); return; }
    if (!$("#confirm-import")?.checked) { toast("Confirm that you reviewed the preview and validation results.", "error"); return; }
    const form = new FormData(); form.append("file", state.data.uploadFile); form.append("confirm", "true");
    setBusy(true, "Importing dataset rows and recording rejected-row audit…");
    try {
      state.data.importResult = await api("/api/data/import", { method: "POST", body: form });
      state.data.validation = null; state.data.uploadFile = null;
      await renderPage();
      toast(`Historical import complete · ${state.data.importResult.accepted_rows} accepted · ${state.data.importResult.rejected_rows} rejected.`);
    } catch (error) { setBusy(false); showError(error.message); }
  }

  document.addEventListener("click", async (event) => {
    const pageButton = event.target.closest("[data-page]");
    if (pageButton) {
      event.preventDefault();
      state.page = pageButton.dataset.page;
      $("#sidebar").classList.remove("open");
      await renderPage();
      return;
    }
    const actionButton = event.target.closest("[data-action]");
    if (!actionButton) return;
    const action = actionButton.dataset.action;
    try {
      if (action === "retry-page") await renderPage();
      else if (action === "inventory-page") { state.inventoryFilters.page = Number(actionButton.dataset.pageNumber); await renderPage(); }
      else if (action === "sales-page") { state.salesFilters.page = Number(actionButton.dataset.pageNumber); await renderPage(); }
      else if (action === "toggle-site") await toggleCatalogue("site", actionButton.dataset.id, actionButton.dataset.active);
      else if (action === "toggle-material") await toggleCatalogue("material", actionButton.dataset.id, actionButton.dataset.active);
      else if (action === "validate-upload") await validateUpload();
      else if (action === "import-upload") await importUpload();
      else if (action === "create-po-from-recommendation") {
        const result = state.replenishmentResult;
        if (!result?.recommendation || result.recommendation.recommended_order_qty <= 0) throw new Error("Calculate a positive replenishment recommendation first.");
        const supplierId = $("#recommendation-supplier")?.value;
        if (!supplierId) throw new Error("Add and select a supplier before creating a purchase order.");
        const payload = { idempotency_key: newIdempotencyKey(), supplier_id: Number(supplierId), site_id: Number(actionButton.dataset.site), material_id: Number(actionButton.dataset.material), quantity: result.recommendation.recommended_order_qty, unit: result.unit, unit_price_inr: numberOrNull($("#recommendation-price")?.value) ?? 0, expected_delivery_date: $("#recommendation-date")?.value || null };
        const created = await api("/api/purchase-orders/from-recommendation", { method: "POST", body: payload });
        toast(`Created ${created.po_number} as Draft.`); await renderPage();
      }
      else if (action === "po-approve") {
        await api(`/api/purchase-orders/${actionButton.dataset.id}/status`, { method: "PATCH", body: { status: actionButton.dataset.status } });
        toast(`Purchase order ${actionButton.dataset.status.toLowerCase()}.`); await renderPage();
      }
      else if (action === "receive-po-line") {
        const qtyValue = prompt(`Quantity to receive (up to ${actionButton.dataset.outstanding} ${actionButton.dataset.unit}):`, actionButton.dataset.outstanding);
        if (qtyValue === null) return;
        const reference = prompt("Receipt reference:", `GRN-${Date.now()}`);
        if (!reference) return;
        await api("/api/receipts", { method: "POST", body: { idempotency_key: newIdempotencyKey(), receipt_reference: reference, purchase_order_line_id: Number(actionButton.dataset.line), quantity: Number(qtyValue), unit: actionButton.dataset.unit, receipt_date: todayString } });
        toast("Goods received and stock ledger updated."); await renderPage();
      }
    } catch (error) { toast(error.message, "error"); }
  });

  document.addEventListener("submit", async (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    const handlers = {
      "dashboard-filter-form": submitDashboardFilter,
      "transaction-form": submitTransaction,
      "inventory-filter-form": submitInventoryFilter,
      "sale-form": submitSale,
      "customer-form": submitCustomer,
      "sales-filter-form": submitSalesFilter,
      "forecast-form": submitForecast,
      "reorder-rule-form": submitReorderRule,
      "replenishment-form": submitReplenishment,
      "site-create-form": createSite,
      "site-update-form": updateSite,
      "material-create-form": createMaterial,
      "material-update-form": updateMaterial,
      "supplier-form": async (form) => { const fd = new FormData(form); await api("/api/suppliers", { method: "POST", body: Object.fromEntries(fd.entries()) }); toast("Supplier added."); await renderPage(); },
    };
    const handler = handlers[form.id];
    if (!handler) return;
    event.preventDefault();
    if (form.dataset.submitting === "true") return;
    form.dataset.submitting = "true";
    const submitButtons = Array.from(form.querySelectorAll('button[type="submit"]'));
    submitButtons.forEach((button) => { button.disabled = true; });
    try {
      setBusy(true, "Saving validated changes…");
      await handler(form);
    } catch (error) {
      setBusy(false);
      showError(error.message, form.closest(".panel") || form.closest(".form-panel") || pageView);
    } finally {
      if (form.isConnected) {
        form.dataset.submitting = "false";
        submitButtons.forEach((button) => { button.disabled = false; });
      }
    }
  });

  document.addEventListener("change", (event) => {
    const target = event.target;
    if (target.id === "txn-kind") updateTransactionFields();
    if (target.id === "csv-file") {
      state.data.uploadFile = target.files?.[0] || null;
      state.data.validation = null;
      state.data.importResult = null;
      const note = target.parentElement?.nextElementSibling?.querySelector(".field-help");
      if (note) note.textContent = state.data.uploadFile?.name || "No file selected";
    }
    if (target.matches('.forecast-model-toggle')) {
      state.forecastVisibleModels = $$(".forecast-model-toggle:checked").map((input) => input.value);
      if (state.forecastResult) drawForecast(state.forecastResult);
    }
  });

  $("#refresh-button").addEventListener("click", async () => {
    try { await loadCatalog(false); await renderPage(); toast("Local data refreshed.", "info"); }
    catch (error) { toast(error.message, "error"); }
  });
  $("#mobile-menu").addEventListener("click", () => $("#sidebar").classList.toggle("open"));
  $("#today-label").textContent = new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", year: "numeric" }).format(today);

  (async function init() {
    try {
      await loadCatalog(false);
      await renderPage();
    } catch (error) {
      setBusy(false);
      pageView.innerHTML = `<div class="page-heading"><div><div class="eyebrow">Local API</div><h1>Service unavailable</h1><p class="page-description">Start the FastAPI server and reload this page.</p></div></div><div class="error-state">${esc(error.message)}</div>`;
    }
  })();
})();
