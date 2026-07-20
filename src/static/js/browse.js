/* Browse Jobs tab */
(function (global) {
  const PAGE_SIZE = 20;
  let state = {
    q: "",
    location: "",
    remote: "",
    experience_max: "",
    salary_min: "",
    seniority: "",
    posted_within_hours: "",
    visa: false,
    sort: "newest",
    offset: 0,
    total: 0,
    expandedId: null,
  };

  const $ = (sel, root) => (root || document).querySelector(sel);

  function buildBrowseDOM() {
    const root = document.getElementById("browse-root");
    const ph = document.getElementById("browse-placeholder");
    if (!root) return;
    if (ph) ph.hidden = true;
    root.hidden = false;
    root.innerHTML = `
      <div class="search-bar">
        <input type="search" id="browse-q" placeholder="Search jobs... e.g. backend engineer, ML, product manager" />
        <button type="button" class="search-icon-btn" id="browse-search-btn" aria-label="Search">
          <svg viewBox="0 0 24 24" width="22" height="22"><path fill="currentColor" d="M15.5 14h-.79l-.28-.27A6.47 6.47 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>
        </button>
      </div>
      <div class="filter-row" id="browse-filters">
        <label>Location<input list="loc-suggestions" id="f-location" type="text" placeholder="City or Remote" /></label>
        <datalist id="loc-suggestions"></datalist>
        <label>Remote
          <select id="f-remote">
            <option value="">Any</option>
            <option value="remote">Remote</option>
            <option value="hybrid">Hybrid</option>
            <option value="onsite">On-site</option>
          </select>
        </label>
        <label>Experience
          <select id="f-experience">
            <option value="">Any</option>
            <option value="2">Entry level (0-2)</option>
            <option value="5">Mid (3-5)</option>
            <option value="8">Senior (5-8)</option>
            <option value="staff">Staff+ (8+)</option>
          </select>
        </label>
        <label>Salary min
          <select id="f-salary">
            <option value="">Any</option>
            <option value="80000">$80K+</option>
            <option value="100000">$100K+</option>
            <option value="120000">$120K+</option>
            <option value="150000">$150K+</option>
            <option value="180000">$180K+</option>
            <option value="200000">$200K+</option>
            <option value="250000">$250K+</option>
          </select>
        </label>
        <label>Seniority
          <select id="f-seniority">
            <option value="">Any</option>
            <option value="intern">Intern</option>
            <option value="junior">Junior</option>
            <option value="mid">Mid</option>
            <option value="senior">Senior</option>
            <option value="staff">Staff</option>
            <option value="principal">Principal</option>
            <option value="lead">Lead</option>
          </select>
        </label>
        <label>Posted
          <select id="f-posted">
            <option value="">Any</option>
            <option value="24">Past 24 hours</option>
            <option value="168">Past 7 days</option>
            <option value="720">Past 30 days</option>
          </select>
        </label>
        <label class="check-label"><input type="checkbox" id="f-visa" /> Sponsors visa</label>
        <button type="button" class="link-btn" id="f-clear">Clear all</button>
      </div>
      <div class="filter-pills" id="filter-pills"></div>
      <div class="results-toolbar">
        <span id="results-count"></span>
        <label>Sort by
          <select id="f-sort">
            <option value="newest">Newest first</option>
            <option value="salary_high">Salary (high to low)</option>
            <option value="salary_low">Salary (low to high)</option>
          </select>
        </label>
      </div>
      <div id="browse-results"></div>
      <div class="pagination" id="browse-pagination"></div>
    `;
    $("#browse-search-btn").addEventListener("click", () => runSearch(0));
    $("#browse-q").addEventListener("keydown", (e) => {
      if (e.key === "Enter") runSearch(0);
    });
    $("#f-clear").addEventListener("click", clearFilters);
    ["f-remote", "f-experience", "f-salary", "f-seniority", "f-posted", "f-sort"].forEach((id) => {
      $( "#" + id ).addEventListener("change", () => runSearch(0));
    });
    $("#f-visa").addEventListener("change", () => runSearch(0));
    $("#f-location").addEventListener("change", () => runSearch(0));
    $("#f-location").addEventListener("input", debounce(loadLocSuggestions, 200));
    loadLocSuggestions();
  }

  function debounce(fn, ms) {
    let t;
    return (...a) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...a), ms);
    };
  }

  async function loadLocSuggestions() {
    const input = $("#f-location");
    const list = $("#loc-suggestions");
    if (!input || !list) return;
    try {
      const data = await global.HireLoopAPI.metaLocations(input.value);
      list.innerHTML = (data.suggestions || [])
        .map((s) => `<option value="${escapeAttr(s)}"></option>`)
        .join("");
    } catch (_) {
      /* ignore */
    }
  }

  function escapeAttr(s) {
    return String(s).replace(/"/g, "&quot;");
  }

  function readFilters() {
    state.q = ($("#browse-q") && $("#browse-q").value.trim()) || "";
    state.location = ($("#f-location") && $("#f-location").value.trim()) || "";
    state.remote = ($("#f-remote") && $("#f-remote").value) || "";
    const exp = ($("#f-experience") && $("#f-experience").value) || "";
    state.experience_max = exp === "staff" ? "" : exp;
    state.salary_min = ($("#f-salary") && $("#f-salary").value) || "";
    state.seniority = ($("#f-seniority") && $("#f-seniority").value) || "";
    state.posted_within_hours = ($("#f-posted") && $("#f-posted").value) || "";
    state.visa = !!( $("#f-visa") && $("#f-visa").checked );
    state.sort = ($("#f-sort") && $("#f-sort").value) || "newest";
  }

  function clearFilters() {
    if ($("#browse-q")) $("#browse-q").value = "";
    if ($("#f-location")) $("#f-location").value = "";
    if ($("#f-remote")) $("#f-remote").value = "";
    if ($("#f-experience")) $("#f-experience").value = "";
    if ($("#f-salary")) $("#f-salary").value = "";
    if ($("#f-seniority")) $("#f-seniority").value = "";
    if ($("#f-posted")) $("#f-posted").value = "";
    if ($("#f-visa")) $("#f-visa").checked = false;
    if ($("#f-sort")) $("#f-sort").value = "newest";
    runSearch(0);
  }

  function postedLabel(hours) {
    if (hours === "24") return "Past 24 hours";
    if (hours === "168") return "Past 7 days";
    if (hours === "720") return "Past 30 days";
    return hours;
  }

  function renderPills() {
    const box = $("#filter-pills");
    if (!box) return;
    const pills = [];
    if (state.location) pills.push(["location", "Location: " + state.location]);
    if (state.remote) pills.push(["remote", "Remote: " + state.remote]);
    if (state.experience_max) pills.push(["experience_max", "Experience: ≤" + state.experience_max]);
    if (state.salary_min) pills.push(["salary_min", "Salary: $" + Number(state.salary_min) / 1000 + "K+"]);
    if (state.seniority) pills.push(["seniority", "Seniority: " + state.seniority]);
    if (state.posted_within_hours)
      pills.push(["posted", "Posted: " + postedLabel(state.posted_within_hours)]);
    if (state.visa) pills.push(["visa", "Sponsors visa"]);
    box.innerHTML = pills
      .map(
        ([key, label]) =>
          `<span class="pill">${label} <button type="button" data-clear="${key}" aria-label="Remove">×</button></span>`
      )
      .join("");
    box.querySelectorAll("button[data-clear]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const k = btn.getAttribute("data-clear");
        if (k === "location" && $("#f-location")) $("#f-location").value = "";
        if (k === "remote" && $("#f-remote")) $("#f-remote").value = "";
        if (k === "experience_max" && $("#f-experience")) $("#f-experience").value = "";
        if (k === "salary_min" && $("#f-salary")) $("#f-salary").value = "";
        if (k === "seniority" && $("#f-seniority")) $("#f-seniority").value = "";
        if (k === "posted" && $("#f-posted")) $("#f-posted").value = "";
        if (k === "visa" && $("#f-visa")) $("#f-visa").checked = false;
        runSearch(0);
      });
    });
  }

  function skeletons() {
    return `<div class="skeleton-card"></div><div class="skeleton-card"></div><div class="skeleton-card"></div>`;
  }

  async function runSearch(offset) {
    readFilters();
    state.offset = offset || 0;
    renderPills();
    const results = $("#browse-results");
    const count = $("#results-count");
    if (results) results.innerHTML = skeletons();
    if (window.HireLoopUI) window.HireLoopUI.clearError();
    const params = {
      q: state.q || undefined,
      location: state.location || undefined,
      remote: state.remote || undefined,
      experience_max: state.experience_max || undefined,
      salary_min: state.salary_min || undefined,
      seniority: state.seniority || undefined,
      posted_within_hours: state.posted_within_hours || undefined,
      visa_sponsorship: state.visa ? "true" : undefined,
      sort: state.sort,
      limit: PAGE_SIZE,
      offset: state.offset,
    };
    try {
      const data = await global.HireLoopAPI.searchJobs(params);
      state.total = data.total_results || 0;
      const showing = (data.jobs || []).length;
      const from = state.total === 0 ? 0 : state.offset + 1;
      const to = state.offset + showing;
      if (count) {
        count.textContent =
          state.total === 0
            ? "No jobs"
            : "Showing " + from + "-" + to + " of " + state.total.toLocaleString() + " jobs";
      }
      if (!showing) {
        results.innerHTML =
          '<div class="placeholder-panel">No jobs found matching your filters. Try broadening your search or removing some filters.</div>';
        $("#browse-pagination").innerHTML = "";
        return;
      }
      results.innerHTML = "";
      (data.jobs || []).forEach((job) => {
        results.appendChild(
          global.HireLoopUI.renderJobCard(job, {
            onExpand: toggleExpand,
            onCompany: (name) => {
              if (global.HireLoopApp && global.HireLoopApp.showCompany) {
                global.HireLoopApp.showCompany(name);
              }
            },
            tapExpand: window.matchMedia("(max-width: 767px)").matches,
          })
        );
      });
      renderPagination();
      if (window.HireLoopApp && window.HireLoopApp.onTabChange) {
        window.HireLoopApp.onTabChange("browse");
      }
    } catch (e) {
      if (results) results.innerHTML = "";
      if (window.HireLoopUI) {
        window.HireLoopUI.showError(
          e.name === "AbortError"
            ? "Search is taking longer than expected. Try again."
            : "HireLoop API is not running. Start it with: docker compose up"
        );
      }
    }
  }

  function renderPagination() {
    const box = $("#browse-pagination");
    if (!box) return;
    const pages = Math.max(1, Math.ceil(state.total / PAGE_SIZE));
    const page = Math.floor(state.offset / PAGE_SIZE) + 1;
    box.innerHTML = `
      <button type="button" class="btn btn-secondary" id="page-prev" ${page <= 1 ? "disabled" : ""}>← Previous</button>
      <span>Page ${page} of ${pages}</span>
      <button type="button" class="btn btn-secondary" id="page-next" ${page >= pages ? "disabled" : ""}>Next →</button>
    `;
    const prev = $("#page-prev");
    const next = $("#page-next");
    if (prev) prev.addEventListener("click", () => runSearch(Math.max(0, state.offset - PAGE_SIZE)));
    if (next) next.addEventListener("click", () => runSearch(state.offset + PAGE_SIZE));
  }

  async function toggleExpand(jobId, card) {
    const body = card.querySelector(".job-expand");
    if (!body) return;
    if (state.expandedId === jobId) {
      body.hidden = true;
      state.expandedId = null;
      return;
    }
    document.querySelectorAll(".job-expand").forEach((n) => (n.hidden = true));
    state.expandedId = jobId;
    body.hidden = false;
    body.innerHTML = "<p class='muted'>Loading details…</p>";
    try {
      const detail = await global.HireLoopAPI.getJob(jobId);
      body.innerHTML = global.HireLoopUI.renderJobDetail(detail);
      const collapse = body.querySelector("[data-collapse]");
      if (collapse) {
        collapse.addEventListener("click", () => {
          body.hidden = true;
          state.expandedId = null;
        });
      }
    } catch (e) {
      body.innerHTML = "<p class='muted'>Could not load details.</p>";
    }
  }

  function init() {
    buildBrowseDOM();
    runSearch(0);
  }

  global.HireLoopBrowse = { init, runSearch, getState: () => state };
})(window);
