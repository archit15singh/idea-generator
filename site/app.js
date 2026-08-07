/* Idea Board client — browse / research from board.json */
(() => {
  const $ = (id) => document.getElementById(id);
  const state = {
    board: null,
    view: "ideas",
    q: "",
    market: "",
    wedgeType: "",
    minFit: 0,
    dgOnly: true,
    ossOnly: false,
    ycOnly: false,
  };

  const esc = (s) =>
    String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");

  const text = (s) => (s == null || s === "" ? "—" : String(s));

  function hay(s) {
    const parts = [
      s.startup,
      s.website,
      s.category,
      s.yc_batch,
      s.core_problem,
      s.key_features,
      s.positioning,
      s.icp,
      s.primary?.description,
      s.primary?.wedge_type,
      ...(s.shortlist || []).map((w) => w.description),
      ...(s.shortlist || []).map((w) => w.wedge_type),
    ];
    return parts.filter(Boolean).join(" ").toLowerCase();
  }

  function renderMeta() {
    const m = state.board.meta;
    $("metaBar").innerHTML = [
      chip(`${m.startups}`, "companies"),
      chip(`${m.wedges}`, "ideas"),
      chip(`${m.decision_grade_primaries}`, "decision-grade", true),
      chip(`${m.markets}`, "markets"),
      chip(`${m.patterns}`, "patterns"),
      chip(`${m.avg_fit}`, "avg fit"),
    ].join("");
  }

  function chip(v, label, accent) {
    return `<span class="chip${accent ? " accent" : ""}"><b>${esc(v)}</b> ${esc(label)}</span>`;
  }

  function fillFilters() {
    const startups = state.board.startups;
    const markets = [...new Set(startups.map((s) => s.category).filter(Boolean))].sort();
    const types = [
      ...new Set(
        startups.flatMap((s) => [s.primary, ...(s.shortlist || [])].filter(Boolean).map((w) => w.wedge_type))
      ),
    ].sort();

    $("market").innerHTML =
      `<option value="">All markets</option>` +
      markets.map((m) => `<option value="${esc(m)}">${esc(m)}</option>`).join("");
    $("wedgeType").innerHTML =
      `<option value="">All wedge types</option>` +
      types.map((t) => `<option value="${esc(t)}">${esc(t)}</option>`).join("");
  }

  function filterStartups() {
    const q = state.q.trim().toLowerCase();
    return state.board.startups.filter((s) => {
      if (state.dgOnly && !s.decision_grade) return false;
      if (state.ossOnly && !s.open_source) return false;
      if (state.ycOnly && !(s.yc_batch && String(s.yc_batch).trim())) return false;
      if (state.market && s.category !== state.market) return false;
      if (state.wedgeType) {
        const types = [s.primary, ...(s.shortlist || [])].filter(Boolean).map((w) => w.wedge_type);
        if (!types.includes(state.wedgeType)) return false;
      }
      if ((s.fit_total || 0) < state.minFit) return false;
      if (q && !hay(s).includes(q)) return false;
      return true;
    });
  }

  function renderIdeas() {
    const rows = filterStartups();
    $("resultsTitle").textContent = "Ideas";
    $("resultsCount").textContent = `${rows.length} of ${state.board.startups.length}`;
    $("ideaFilters").classList.remove("hidden");
    const list = $("list");
    if (!rows.length) {
      list.innerHTML = "";
      $("empty").classList.remove("hidden");
      return;
    }
    $("empty").classList.add("hidden");
    list.innerHTML = rows
      .map((s) => {
        const p = s.primary;
        const idea = p?.description || "No primary idea";
        const type = p?.wedge_type || "—";
        return `
          <button type="button" class="card" role="listitem" data-id="${s.id}">
            <div>
              <p class="card-name">${esc(s.startup)}</p>
              <p class="card-meta">${esc(s.category || "Uncategorized")}${s.yc_batch ? " · " + esc(s.yc_batch) : ""}</p>
            </div>
            <p class="card-idea"><strong>${esc(type)}</strong>${esc(idea)}</p>
            <div class="card-side">
              <div class="fit">${esc(s.fit_total ?? "—")}<small>FIT</small></div>
              <div class="badges">
                ${s.decision_grade ? `<span class="badge ok">grade</span>` : `<span class="badge">raw</span>`}
                ${s.open_source ? `<span class="badge">oss</span>` : ""}
                ${p?.personal_fit_score != null ? `<span class="badge warn">w ${esc(p.personal_fit_score)}</span>` : ""}
              </div>
            </div>
          </button>`;
      })
      .join("");

    list.querySelectorAll(".card").forEach((el) => {
      el.addEventListener("click", () => openStartup(+el.dataset.id));
    });
  }

  function renderPatterns() {
    $("ideaFilters").classList.add("hidden");
    $("resultsTitle").textContent = "Patterns";
    let rows = state.board.patterns || [];
    const q = state.q.trim().toLowerCase();
    if (q) rows = rows.filter((p) => (p.canonical_name + " " + (p.mini_spec || "")).toLowerCase().includes(q));
    $("resultsCount").textContent = `${rows.length} patterns`;
    if (!rows.length) {
      $("list").innerHTML = "";
      $("empty").classList.remove("hidden");
      return;
    }
    $("empty").classList.add("hidden");
    $("list").innerHTML = rows
      .map(
        (p) => `
      <button type="button" class="pat-card" data-pid="${p.id}">
        <span class="sight">${esc(p.sightings)} sights</span>
        <h3>${esc(p.canonical_name)}</h3>
        <p>${esc((p.mini_spec || "Promoted cluster pattern").slice(0, 180))}</p>
      </button>`
      )
      .join("");
  }

  function renderMarkets() {
    $("ideaFilters").classList.add("hidden");
    $("resultsTitle").textContent = "Markets";
    let rows = state.board.markets || [];
    const q = state.q.trim().toLowerCase();
    if (q) rows = rows.filter((m) => (m.parent_market + " " + (m.segs_list || "")).toLowerCase().includes(q));
    $("resultsCount").textContent = `${rows.length} top-level markets`;
    if (!rows.length) {
      $("list").innerHTML = "";
      $("empty").classList.remove("hidden");
      return;
    }
    $("empty").classList.add("hidden");
    const counts = {};
    for (const s of state.board.startups) {
      if (!s.category) continue;
      counts[s.category] = (counts[s.category] || 0) + 1;
    }
    $("list").innerHTML = rows
      .map((m) => {
        const n = counts[m.parent_market] || 0;
        return `
        <button type="button" class="mkt-card" data-market="${esc(m.parent_market)}">
          <span class="sight">${n} cos · ${esc(m.segs)} segs</span>
          <h3>${esc(m.parent_market)}</h3>
          <p>${esc((m.segs_list || "").slice(0, 200))}</p>
        </button>`;
      })
      .join("");
    $("list").querySelectorAll(".mkt-card").forEach((el) => {
      el.addEventListener("click", () => {
        state.view = "ideas";
        state.market = el.dataset.market;
        $("market").value = state.market;
        document.querySelectorAll(".seg-btn").forEach((b) => {
          const on = b.dataset.view === "ideas";
          b.classList.toggle("active", on);
          b.setAttribute("aria-selected", on ? "true" : "false");
        });
        render();
      });
    });
  }

  function renderInfra() {
    $("ideaFilters").classList.add("hidden");
    $("resultsTitle").textContent = "Infrastructure layers";
    let rows = state.board.infra || [];
    const q = state.q.trim().toLowerCase();
    if (q) rows = rows.filter((x) => (x.canonical_name + " " + (x.internal_platform || "")).toLowerCase().includes(q));
    $("resultsCount").textContent = `${rows.length} layers`;
    if (!rows.length) {
      $("list").innerHTML = "";
      $("empty").classList.remove("hidden");
      return;
    }
    $("empty").classList.add("hidden");
    $("list").innerHTML = rows
      .map(
        (x) => `
      <div class="pat-card" style="cursor:default">
        <span class="sight">${esc(x.sightings)}${x.convergence ? " · convergent" : ""}</span>
        <h3>${esc(x.canonical_name)}</h3>
        <p>${esc(x.internal_platform || x.mini_spec || "—")}</p>
      </div>`
      )
      .join("");
  }

  function render() {
    if (state.view === "ideas") renderIdeas();
    else if (state.view === "patterns") renderPatterns();
    else if (state.view === "markets") renderMarkets();
    else renderInfra();
  }

  function setDeepLink(id) {
    const url = new URL(location.href);
    if (id == null) url.searchParams.delete("id");
    else url.searchParams.set("id", String(id));
    history.replaceState(null, "", url.pathname + url.search + url.hash);
  }

  function openStartup(id) {
    const s = state.board.startups.find((x) => x.id === id);
    if (!s) return;
    $("dEyebrow").textContent = [s.category, s.stage_marker, s.yc_batch].filter(Boolean).join(" · ");
    $("dTitle").textContent = s.startup;
    $("dSub").textContent = s.website || "";
    const axes = [
      ["Technical", s.technical_advantage],
      ["Interest", s.interest],
      ["Knowledge", s.existing_knowledge],
      ["Sales", s.sales_ability],
      ["Moat", s.long_term_moat],
      ["Build speed", s.build_speed],
      ["Market", s.market_size],
      ["Distribution", s.distribution_fit],
    ];
    const ideas = [s.primary, ...(s.shortlist || [])].filter(Boolean);
    const more = (s.wedges || []).filter((w) => !w.selected || w.selected === 0).slice(0, 8);

    $("dBody").innerHTML = `
      <div class="section">
        <h3>Founder fit · ${esc(s.fit_total ?? "—")}</h3>
        <div class="fit-grid">${axes.map(([k, v]) => `<div><span>${esc(k)}</span> <b>${esc(v ?? "—")}</b></div>`).join("")}</div>
        ${s.website ? `<a class="link-out" href="${esc(s.website)}" target="_blank" rel="noopener">Open website ↗</a>` : ""}
      </div>
      <div class="section">
        <h3>Primary & shortlist</h3>
        ${ideas
          .map(
            (w) => `
          <div class="idea-block${w.selected === 1 ? " primary" : ""}">
            <div class="type">${esc(w.wedge_type)} · rank ${esc(w.selected)}
              <span class="score">score ${esc(w.personal_fit_score ?? "—")}</span>
            </div>
            <p>${esc(w.description)}</p>
            <p style="font-size:12px;color:var(--paper-mute);margin-top:0.4rem"><em>Evidence:</em> ${esc(w.evidence || "—")}</p>
          </div>`
          )
          .join("") || "<p>No selected ideas.</p>"}
      </div>
      <div class="section"><h3>Problem</h3><p>${esc(text(s.core_problem))}</p>
        <p><em>Why current fails:</em> ${esc(text(s.why_current_fail))}</p></div>
      <div class="section"><h3>Product</h3><p>${esc(text(s.key_features))}</p>
        <p><em>Workflow:</em> ${esc(text(s.core_workflow))}</p></div>
      <div class="section"><h3>ICP</h3><p>${esc(text(s.icp))}</p>
        <p>${esc(text(s.buyer_persona))} · ${esc(text(s.company_size))}</p></div>
      <div class="section"><h3>Competitive</h3>
        <p><em>Moat:</em> ${esc(text(s.moat))}</p>
        <p><em>Weaknesses:</em> ${esc(text(s.weaknesses))}</p>
        <p><em>Direct:</em> ${esc(text(s.direct_competitors))}</p></div>
      <div class="section"><h3>Technical</h3>
        <p>${esc(text(s.likely_architecture))}</p>
        <p class="card-meta" style="margin-top:0.4rem">LLM ${esc(text(s.llms))} · memory ${esc(text(s.memory))} · agents ${esc(text(s.agents))}</p></div>
      ${
        more.length
          ? `<div class="section"><h3>Other wedges (sample)</h3>${more
              .map(
                (w) =>
                  `<div class="idea-block"><div class="type">${esc(w.wedge_type)}</div><p>${esc(w.description || "—")}</p></div>`
              )
              .join("")}</div>`
          : ""
      }
    `;
    setDeepLink(s.id);
    openDrawer();
  }

  function openDrawer() {
    const d = $("drawer");
    d.hidden = false;
    d.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
  }
  function closeDrawer() {
    const d = $("drawer");
    d.hidden = true;
    d.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
    setDeepLink(null);
  }

  function wire() {
    $("q").addEventListener("input", (e) => {
      state.q = e.target.value;
      render();
    });
    $("market").addEventListener("change", (e) => {
      state.market = e.target.value;
      render();
    });
    $("wedgeType").addEventListener("change", (e) => {
      state.wedgeType = e.target.value;
      render();
    });
    $("minFit").addEventListener("input", (e) => {
      state.minFit = +e.target.value;
      $("minFitOut").textContent = state.minFit;
      render();
    });
    $("dgOnly").addEventListener("change", (e) => {
      state.dgOnly = e.target.checked;
      render();
    });
    $("ossOnly").addEventListener("change", (e) => {
      state.ossOnly = e.target.checked;
      render();
    });
    $("ycOnly").addEventListener("change", (e) => {
      state.ycOnly = e.target.checked;
      render();
    });
    document.querySelectorAll(".seg-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.view = btn.dataset.view;
        document.querySelectorAll(".seg-btn").forEach((b) => {
          const on = b === btn;
          b.classList.toggle("active", on);
          b.setAttribute("aria-selected", on ? "true" : "false");
        });
        render();
      });
    });
    $("drawer").addEventListener("click", (e) => {
      if (e.target.matches("[data-close]") || e.target.classList.contains("drawer-backdrop")) closeDrawer();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeDrawer();
      if (e.key === "/" && document.activeElement?.tagName !== "INPUT" && document.activeElement?.tagName !== "SELECT") {
        e.preventDefault();
        $("q").focus();
      }
    });
  }

  async function boot() {
    wire();
    try {
      const res = await fetch("data/board.json", { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      state.board = await res.json();
      renderMeta();
      fillFilters();
      render();
      const deepId = +new URL(location.href).searchParams.get("id");
      if (deepId) openStartup(deepId);
    } catch (err) {
      $("metaBar").textContent = `Failed to load board.json — ${err.message}. Serve via http (not file://).`;
      $("list").innerHTML = "";
      $("empty").classList.remove("hidden");
      $("empty").textContent = "Run: python3 scripts/export_board.py && cd site && python3 -m http.server 8765";
    }
  }

  boot();
})();
