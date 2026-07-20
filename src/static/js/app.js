/* Main app — tabs + stats pill + company view */
(function () {
  function setTab(name) {
    document.querySelectorAll(".tab-btn").forEach((btn) => {
      const on = btn.dataset.tab === name;
      btn.classList.toggle("active", on);
      btn.setAttribute("aria-selected", on ? "true" : "false");
    });
    document.querySelectorAll(".tab-panel").forEach((panel) => {
      const isCompany = panel.id === "company-view";
      if (isCompany) return;
      const on = panel.id === "panel-" + name;
      panel.classList.toggle("active", on);
      panel.hidden = !on;
    });
    const company = document.getElementById("company-view");
    if (company) {
      company.hidden = true;
      company.classList.remove("active");
    }
    if (name === "matches" && window.HireLoopMatches) {
      window.HireLoopMatches.onTabShow();
    }
    if (window.HireLoopApp && window.HireLoopApp.onTabChange) {
      window.HireLoopApp.onTabChange(name);
    }
  }

  async function loadStats() {
    const pill = document.getElementById("stats-pill");
    try {
      const s = await window.HireLoopAPI.getStats();
      const jobs = (s.total_active_jobs || 0).toLocaleString();
      const cos = (s.total_companies || 0).toLocaleString();
      const fresh = s.data_freshness || "unknown";
      if (pill) pill.textContent = jobs + " jobs · " + cos + " companies · Updated " + fresh;
      const foot = document.getElementById("stats-footer-body");
      if (foot) {
        const topCo = (s.top_companies || [])
          .slice(0, 3)
          .map((c) => c.company_name + " (" + c.active_jobs + ")")
          .join(" ");
        const topRoles = (s.top_roles || [])
          .slice(0, 3)
          .map((r) => r.title || r.role || r.name || "")
          .filter(Boolean)
          .join(" ");
        foot.innerHTML =
          jobs +
          " active jobs · " +
          cos +
          " companies · " +
          (s.total_cities || 0) +
          " cities<br/>" +
          (s.jobs_added_last_24h || 0) +
          " new today · Refreshed every 2 hours<br/>" +
          (topCo ? "Top hiring: " + topCo + "<br/>" : "") +
          (topRoles ? "Top roles: " + topRoles : "");
      }
    } catch (e) {
      if (pill) pill.textContent = "Stats unavailable";
      if (window.HireLoopUI) {
        window.HireLoopUI.showError(
          "HireLoop API is not running. Start it with: docker compose up"
        );
      }
    }
  }

  async function showCompany(name) {
    if (!name) return;
    const view = document.getElementById("company-view");
    const browse = document.getElementById("panel-browse");
    const matches = document.getElementById("panel-matches");
    if (!view) return;
    if (browse) browse.hidden = true;
    if (matches) matches.hidden = true;
    view.hidden = false;
    view.classList.add("active");
    view.innerHTML =
      '<div class="card"><p class="muted">Loading ' +
      window.HireLoopUI.escapeHtml(name) +
      "…</p></div>";
    try {
      let insights = null;
      try {
        insights = await window.HireLoopAPI.companyInsights(name);
      } catch (_) {
        insights = null;
      }
      const jobsPayload = await window.HireLoopAPI.companyJobs(name, { limit: 50 });
      const stack = ((insights && insights.tech_stack) || {}).primary || [];
      const roles = (insights && insights.hiring_by_role) || [];
      const sector = (insights && insights.sector) || "";
      const esc = window.HireLoopUI.escapeHtml;
      view.innerHTML =
        '<button type="button" class="link-btn" id="company-back">← Back to results</button>' +
        '<div class="card" style="margin-top:12px">' +
        "<h2>" +
        esc(jobsPayload.company_name || name) +
        "</h2>" +
        '<p class="muted">' +
        (sector ? esc(sector) + " · " : "") +
        (jobsPayload.active_jobs || 0) +
        " active jobs</p>" +
        "<p><strong>Tech stack:</strong> " +
        (stack.length
          ? stack
              .map(function (s) {
                return '<span class="tag">' + esc(s.skill || s) + "</span>";
              })
              .join("")
          : "—") +
        "</p>" +
        "<p><strong>Top roles:</strong> " +
        (roles.length
          ? roles
              .slice(0, 8)
              .map(function (r) {
                return esc(r.title) + " (" + r.count + ")";
              })
              .join(", ")
          : "—") +
        "</p>" +
        '<div class="filter-row" style="margin-top:12px">' +
        '<label>Department<input type="text" id="co-dept" placeholder="e.g. Engineering" /></label>' +
        "<label>Seniority<select id=\"co-seniority\"><option value=\"\">Any</option>" +
        "<option value=\"intern\">Intern</option><option value=\"junior\">Junior</option>" +
        "<option value=\"mid\">Mid</option><option value=\"senior\">Senior</option>" +
        "<option value=\"staff\">Staff</option><option value=\"principal\">Principal</option>" +
        "<option value=\"lead\">Lead</option></select></label>" +
        '<button type="button" class="btn btn-secondary" id="co-filter">Filter</button>' +
        "</div></div>" +
        '<div id="company-jobs" style="margin-top:16px"></div>';

      function renderJobs(jobs) {
        const box = document.getElementById("company-jobs");
        box.innerHTML = "";
        (jobs || []).forEach(function (job) {
          box.appendChild(
            window.HireLoopUI.renderJobCard(job, {
              onExpand: async function (id, card) {
                const body = card.querySelector(".job-expand");
                if (!body.hidden) {
                  body.hidden = true;
                  return;
                }
                body.hidden = false;
                try {
                  const detail = await window.HireLoopAPI.getJob(id);
                  body.innerHTML = window.HireLoopUI.renderJobDetail(detail);
                } catch (_) {
                  body.innerHTML = "<p class='muted'>Could not load details.</p>";
                }
              },
            })
          );
        });
      }
      renderJobs(jobsPayload.jobs);
      document.getElementById("company-back").addEventListener("click", function () {
        view.hidden = true;
        view.classList.remove("active");
        const activeTab = document.querySelector(".tab-btn.active");
        setTab((activeTab && activeTab.dataset.tab) || "browse");
      });
      document.getElementById("co-filter").addEventListener("click", async function () {
        const dept = document.getElementById("co-dept").value.trim();
        const sen = document.getElementById("co-seniority").value;
        const filtered = await window.HireLoopAPI.companyJobs(name, {
          limit: 50,
          department: dept || undefined,
          seniority: sen || undefined,
        });
        renderJobs(filtered.jobs);
      });
    } catch (e) {
      view.innerHTML =
        '<button type="button" class="link-btn" id="company-back">← Back</button>' +
        '<div class="placeholder-panel">Could not load company.</div>';
      document.getElementById("company-back").addEventListener("click", function () {
        view.hidden = true;
        setTab("browse");
      });
    }
  }

  function writeHash(tab) {
    if (tab === "matches") {
      history.replaceState(null, "", "#matches");
      return;
    }
    if (!window.HireLoopBrowse || !window.HireLoopBrowse.getState) {
      history.replaceState(null, "", "#browse");
      return;
    }
    const st = window.HireLoopBrowse.getState();
    const q = new URLSearchParams();
    if (st.q) q.set("q", st.q);
    if (st.location) q.set("location", st.location);
    if (st.remote) q.set("remote", st.remote);
    if (st.experience_max) q.set("experience_max", st.experience_max);
    if (st.salary_min) q.set("salary_min", st.salary_min);
    if (st.seniority) q.set("seniority", st.seniority);
    if (st.visa) q.set("visa_sponsorship", "true");
    if (st.sort && st.sort !== "newest") q.set("sort", st.sort);
    const qs = q.toString();
    history.replaceState(null, "", "#browse" + (qs ? "?" + qs : ""));
  }

  function applyHash() {
    const raw = (location.hash || "#browse").slice(1);
    const [tabPart, queryPart] = raw.split("?");
    const tab = tabPart === "matches" ? "matches" : "browse";
    setTab(tab);
    if (tab === "browse" && queryPart && window.HireLoopBrowse) {
      const params = new URLSearchParams(queryPart);
      const map = {
        q: "browse-q",
        location: "f-location",
        remote: "f-remote",
        experience_max: "f-experience",
        salary_min: "f-salary",
        seniority: "f-seniority",
        sort: "f-sort",
      };
      Object.keys(map).forEach(function (k) {
        const el = document.getElementById(map[k]);
        if (el && params.has(k)) el.value = params.get(k);
      });
      const visa = document.getElementById("f-visa");
      if (visa) visa.checked = params.get("visa_sponsorship") === "true";
      if (window.HireLoopBrowse.runSearch) window.HireLoopBrowse.runSearch(0);
    }
  }

  async function checkEmptyDb() {
    try {
      const h = await window.HireLoopAPI.getHealth();
      const setup = h.setup || {};
      if (setup.jobs_loaded > 0) return;
      const msg =
        setup.message ||
        "HireLoop is loading job data for the first time. Come back shortly.";
      const browsePh = document.getElementById("browse-placeholder");
      if (browsePh) {
        browsePh.hidden = false;
        browsePh.textContent = msg;
      }
      const root = document.getElementById("browse-root");
      if (root) root.hidden = true;
      const drop = document.getElementById("drop-zone");
      if (drop) drop.style.pointerEvents = "none";
      if (window.HireLoopUI) window.HireLoopUI.showError(msg);
    } catch (_) {}
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".tab-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        setTab(btn.dataset.tab);
        writeHash(btn.dataset.tab);
      });
    });
    const copyBtn = document.getElementById("copy-claude");
    if (copyBtn) {
      copyBtn.addEventListener("click", async function () {
        const pre = document.getElementById("mcp-claude-json");
        try {
          await navigator.clipboard.writeText(pre.textContent);
          copyBtn.textContent = "Copied";
          setTimeout(function () {
            copyBtn.textContent = "Copy";
          }, 1500);
        } catch (_) {}
      });
    }
    document.addEventListener("keydown", function (e) {
      const tag = (e.target && e.target.tagName) || "";
      if (e.key === "/" && tag !== "INPUT" && tag !== "TEXTAREA" && tag !== "SELECT") {
        e.preventDefault();
        setTab("browse");
        const q = document.getElementById("browse-q");
        if (q) q.focus();
      }
      if (e.key === "Escape") {
        document.querySelectorAll(".job-expand").forEach(function (n) {
          n.hidden = true;
        });
      }
    });
    window.addEventListener("popstate", applyHash);
    loadStats();
    if (window.HireLoopBrowse) window.HireLoopBrowse.init();
    if (window.HireLoopMatches) window.HireLoopMatches.init();
    applyHash();
    checkEmptyDb();
  });

  window.HireLoopApp = {
    setTab: setTab,
    showCompany: showCompany,
    onTabChange: function (name) {
      writeHash(name);
    },
  };
})();
