/* My Matches — resume upload, profile, prefs (match results in Task 4) */
(function (global) {
  const PROFILE_KEY = "hireloop_profile";
  const PREFS_KEY = "hireloop_preferences";
  let profile = null;
  let prefs = null;
  let stale = false;
  let pdfLib = null;
  let expandTimer = null;
  let matchPage = {
    offset: 0,
    pageSize: 20,
    total: 0,
    lastData: null,
    nextPoll: null,
  };

  const $ = (sel, root) => (root || document).querySelector(sel);

  function loadStored() {
    try {
      profile = JSON.parse(localStorage.getItem(PROFILE_KEY) || "null");
      prefs = JSON.parse(localStorage.getItem(PREFS_KEY) || "null");
    } catch {
      profile = null;
      prefs = null;
    }
  }

  function saveProfile() {
    localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
  }

  function savePrefs() {
    prefs = readPrefsForm();
    localStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
  }

  function clearAll() {
    profile = null;
    prefs = null;
    localStorage.removeItem(PROFILE_KEY);
    localStorage.removeItem(PREFS_KEY);
    render();
  }

  function buildShell() {
    const root = document.getElementById("matches-root");
    const ph = document.getElementById("matches-placeholder");
    if (!root) return;
    if (ph) ph.hidden = true;
    root.hidden = false;
    root.innerHTML = `
      <div id="matches-upload"></div>
      <div id="matches-profile" hidden></div>
      <div id="matches-results"></div>
    `;
  }

  function renderUpload() {
    const box = $("#matches-upload");
    if (!box) return;
    if (profile && profile.skills && profile.skills.length) {
      box.hidden = true;
      return;
    }
    box.hidden = false;
    box.innerHTML = `
      <div class="upload-zone card" id="drop-zone">
        <h2>Upload your resume</h2>
        <p>Drop your resume here or click to browse. We'll extract your skills and find matching jobs.</p>
        <div class="drop-target" id="drop-target" tabindex="0" role="button">
          <p><strong>Drag & drop PDF here</strong><br/>or click to browse</p>
          <input type="file" id="resume-file" accept="application/pdf,.pdf" hidden />
        </div>
        <p class="muted privacy-note">
          <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V6.3l7-3.11v8.8z"/></svg>
          Your resume is processed locally and never stored on disk.
        </p>
        <p><button type="button" class="link-btn" id="paste-toggle">Paste resume text instead</button></p>
        <div id="paste-box" hidden>
          <textarea id="resume-paste" placeholder="Paste resume text here…"></textarea>
          <button type="button" class="btn btn-primary" id="paste-submit" style="margin-top:8px">Extract skills</button>
        </div>
        <p id="upload-progress" class="muted" hidden></p>
      </div>
    `;
    const zone = $("#drop-target");
    const input = $("#resume-file");
    zone.addEventListener("click", () => input.click());
    zone.addEventListener("dragover", (e) => {
      e.preventDefault();
      zone.classList.add("dragover");
    });
    zone.addEventListener("dragleave", () => zone.classList.remove("dragover"));
    zone.addEventListener("drop", (e) => {
      e.preventDefault();
      zone.classList.remove("dragover");
      const f = e.dataTransfer.files[0];
      if (f) handleFile(f);
    });
    input.addEventListener("change", () => {
      if (input.files[0]) handleFile(input.files[0]);
    });
    $("#paste-toggle").addEventListener("click", () => {
      const pb = $("#paste-box");
      pb.hidden = !pb.hidden;
    });
    $("#paste-submit").addEventListener("click", async () => {
      const text = ($("#resume-paste").value || "").trim();
      if (!text) return;
      await parseText(text);
    });
  }

  function setProgress(msg) {
    const el = $("#upload-progress");
    if (!el) return;
    if (!msg) {
      el.hidden = true;
      el.textContent = "";
      return;
    }
    el.hidden = false;
    el.textContent = msg;
  }

  async function ensurePdfJs() {
    if (pdfLib) return pdfLib;
    // Lazy-load pinned PDF.js 4.0.379 (only when Matches needs it)
    const mod = await import(
      "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.0.379/pdf.min.mjs"
    );
    mod.GlobalWorkerOptions.workerSrc =
      "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.0.379/pdf.worker.min.mjs";
    pdfLib = mod;
    return pdfLib;
  }

  /** Extract text in-browser; PDF binary never uploaded (only resulting string POSTed). */
  async function extractTextFromPDF(file) {
    const pdfjs = await ensurePdfJs();
    const buf = await file.arrayBuffer();
    const pdf = await pdfjs.getDocument({ data: buf }).promise;
    let full = "";
    for (let i = 1; i <= pdf.numPages; i++) {
      const page = await pdf.getPage(i);
      const content = await page.getTextContent();
      full += content.items.map((it) => it.str).join(" ") + "\n";
    }
    if (!full.trim()) {
      throw new Error("empty-text-layer");
    }
    return full.trim();
  }

  async function handleFile(file) {
    if (!file || file.type !== "application/pdf") {
      showPasteFallback("Please upload a PDF file.");
      return;
    }
    try {
      setProgress("Reading resume…");
      const text = await extractTextFromPDF(file);
      if (!text) {
        showPasteFallback("Couldn't read this PDF. Try pasting your resume text instead.");
        return;
      }
      await parseText(text);
    } catch (e) {
      showPasteFallback("Couldn't read this PDF. Try pasting your resume text instead.");
    }
  }

  function showPasteFallback(msg) {
    setProgress("");
    if (window.HireLoopUI) window.HireLoopUI.showError(msg);
    const pb = $("#paste-box");
    if (pb) pb.hidden = false;
  }

  async function parseText(text) {
    try {
      setProgress("Extracting skills…");
      if (window.HireLoopUI) window.HireLoopUI.clearError();
      profile = await global.HireLoopAPI.parseResume({ resume_text: text });
      saveProfile();
      if (!prefs) prefs = {};
      if (profile.location && !prefs.location) prefs.location = profile.location;
      if (profile.experience_years && !prefs.experience_level) {
        prefs.experience_level = yearsToLevel(profile.experience_years);
      }
      if (profile.past_roles && profile.past_roles[0] && !prefs.target_role) {
        prefs.target_role = profile.past_roles[0].split(" at ")[0];
      }
      savePrefs();
      setProgress("");
      render();
    } catch (e) {
      setProgress("");
      if (window.HireLoopUI) {
        window.HireLoopUI.showError(
          "Couldn't process this resume. Try pasting the text instead."
        );
      }
      showPasteFallback("");
    }
  }

  function yearsToLevel(y) {
    if (y <= 2) return "entry";
    if (y <= 5) return "mid";
    if (y <= 8) return "senior";
    return "staff";
  }

  function levelToYears(level) {
    return { entry: 1, mid: 4, senior: 6, staff: 10 }[level] || null;
  }

  function renderProfile() {
    const box = $("#matches-profile");
    if (!box) return;
    if (!profile || !profile.skills) {
      box.hidden = true;
      return;
    }
    box.hidden = false;
    const inferred = (profile.inferred || [])
      .map((s) => {
        const conf = Math.round((s.confidence || 0) * 100);
        const from = s.inferred_from ? ` (from ${s.inferred_from}, ${conf}%)` : ` (${conf}%)`;
        return `<span class="tag tag-inferred">${escape(s.name)}${from}</span>`;
      })
      .join("");
    const direct = (profile.skills || [])
      .map(
        (s) =>
          `<span class="tag skill-tag">${escape(s)} <button type="button" data-rm="${escape(s)}" aria-label="Remove">×</button></span>`
      )
      .join("");
    const roles = (profile.past_roles || [])
      .map((r) => `<span class="tag tag-gray">${escape(r)}</span>`)
      .join("");
    const p = prefs || {};
    box.innerHTML = `
      <div class="matches-layout">
        <div class="card">
          <h2>Your Skills</h2>
          <p class="muted">Direct skills:</p>
          <div class="job-skills" id="direct-skills">${direct}</div>
          <input type="text" id="add-skill" placeholder="Add skill + Enter" />
          <p class="muted" style="margin-top:12px">Inferred skills:</p>
          <div class="job-skills">${inferred || "<span class='muted'>None yet</span>"}</div>
          <p class="muted" style="margin-top:12px">Detected from your resume:</p>
          <div class="job-skills">${roles || "—"}</div>
          <label>Experience (years)<input type="number" id="prof-years" value="${profile.experience_years ?? ""}" min="0" max="40" /></label>
          <label>Location<input type="text" id="prof-location" list="role-loc-list" value="${escape(profile.location || "")}" /></label>
          <datalist id="role-loc-list"></datalist>
          <p class="muted">Contact: ${escape(profile.contact?.email || "—")} · ${escape(profile.contact?.linkedin || "")} · ${escape(profile.contact?.github || "")}</p>
          <p>Looks right? Edit anything that doesn't look right, then set your preferences.</p>
          <button type="button" class="link-btn" id="clear-profile">Clear profile</button>
        </div>
        <div class="card">
          <h2>What are you looking for?</h2>
          <label>Target role<input type="text" id="pref-role" list="role-suggestions" value="${escape(p.target_role || "")}" /></label>
          <datalist id="role-suggestions"></datalist>
          <label>Location<input type="text" id="pref-location" value="${escape(p.location || profile.location || "")}" /></label>
          <label class="toggle"><span>Open to remote</span>
            <input type="checkbox" id="pref-remote" ${p.remote_ok !== false ? "checked" : ""} />
            <span class="toggle-track" aria-hidden="true"></span>
          </label>
          <label>Minimum salary
            <select id="pref-salary">
              <option value="">None</option>
              ${[80, 100, 120, 150, 180, 200, 250]
                .map(
                  (k) =>
                    `<option value="${k * 1000}" ${String(p.salary_min) === String(k * 1000) ? "selected" : ""}>$${k}K</option>`
                )
                .join("")}
            </select>
          </label>
          <label>Experience level
            <select id="pref-exp">
              <option value="">Any</option>
              <option value="entry" ${p.experience_level === "entry" ? "selected" : ""}>Entry</option>
              <option value="mid" ${p.experience_level === "mid" ? "selected" : ""}>Mid</option>
              <option value="senior" ${p.experience_level === "senior" ? "selected" : ""}>Senior</option>
              <option value="staff" ${p.experience_level === "staff" ? "selected" : ""}>Staff+</option>
            </select>
          </label>
          <label>Seniority
            <select id="pref-seniority">
              <option value="">Any</option>
              ${["intern", "junior", "mid", "senior", "staff", "principal", "lead"]
                .map(
                  (s) =>
                    `<option value="${s}" ${p.seniority === s ? "selected" : ""}>${s}</option>`
                )
                .join("")}
            </select>
          </label>
          <label class="toggle"><span>Need visa sponsorship</span>
            <input type="checkbox" id="pref-visa" ${p.visa_needed ? "checked" : ""} />
            <span class="toggle-track" aria-hidden="true"></span>
          </label>
          <label>Specific companies<input type="text" id="pref-companies" placeholder="Stripe, Anthropic" value="${escape(p.companies || "")}" /></label>
          <label>Posted
            <select id="pref-posted">
              <option value="">Any</option>
              <option value="24" ${String(p.posted_within_hours) === "24" ? "selected" : ""}>Past 24 hours</option>
              <option value="168" ${String(p.posted_within_hours) === "168" ? "selected" : ""}>Past 7 days</option>
              <option value="720" ${String(p.posted_within_hours) === "720" ? "selected" : ""}>Past 30 days</option>
            </select>
          </label>
        </div>
      </div>
      <button type="button" class="btn btn-primary btn-find-matches ${stale ? "pulse" : ""}" id="find-matches">Find Matches</button>
    `;
    box.querySelectorAll("[data-rm]").forEach((btn) => {
      btn.addEventListener("click", () => removeSkill(btn.getAttribute("data-rm")));
    });
    $("#add-skill").addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        addSkill(e.target.value);
        e.target.value = "";
      }
    });
    $("#clear-profile").addEventListener("click", clearAll);
    $("#prof-years").addEventListener("change", () => {
      profile.experience_years = Number($("#prof-years").value) || null;
      saveProfile();
      markStale();
    });
    $("#prof-location").addEventListener("change", () => {
      profile.location = $("#prof-location").value;
      saveProfile();
      markStale();
    });
    ["pref-role", "pref-location", "pref-salary", "pref-exp", "pref-seniority", "pref-companies", "pref-posted"].forEach(
      (id) => {
        const n = $("#" + id);
        if (n) n.addEventListener("change", () => { savePrefs(); markStale(); });
      }
    );
    $("#pref-remote").addEventListener("change", () => { savePrefs(); markStale(); });
    $("#pref-visa").addEventListener("change", () => { savePrefs(); markStale(); });
    $("#pref-role").addEventListener(
      "input",
      debounce(async () => {
        try {
          const d = await global.HireLoopAPI.metaRoles($("#pref-role").value);
          $("#role-suggestions").innerHTML = (d.suggestions || [])
            .map((s) => `<option value="${escape(s)}"></option>`)
            .join("");
        } catch (_) {}
      }, 200)
    );
    $("#find-matches").addEventListener("click", () => {
      if (global.HireLoopMatches.runMatch) global.HireLoopMatches.runMatch(0);
    });
  }

  function escape(s) {
    return global.HireLoopUI ? global.HireLoopUI.escapeHtml(s) : String(s);
  }

  function debounce(fn, ms) {
    let t;
    return (...a) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...a), ms);
    };
  }

  function readPrefsForm() {
    return {
      target_role: ($("#pref-role") && $("#pref-role").value.trim()) || "",
      location: ($("#pref-location") && $("#pref-location").value.trim()) || "",
      remote_ok: !$("#pref-remote") || $("#pref-remote").checked,
      salary_min: ($("#pref-salary") && $("#pref-salary").value) || "",
      experience_level: ($("#pref-exp") && $("#pref-exp").value) || "",
      seniority: ($("#pref-seniority") && $("#pref-seniority").value) || "",
      visa_needed: !!( $("#pref-visa") && $("#pref-visa").checked ),
      companies: ($("#pref-companies") && $("#pref-companies").value.trim()) || "",
      posted_within_hours: ($("#pref-posted") && $("#pref-posted").value) || "",
    };
  }

  function markStale() {
    stale = true;
    const btn = $("#find-matches");
    if (btn) btn.classList.add("pulse");
  }

  function addSkill(name) {
    name = (name || "").trim();
    if (!name || !profile) return;
    if (!profile.skills.includes(name)) profile.skills.push(name);
    saveProfile();
    scheduleExpand();
    markStale();
    renderProfile();
  }

  function removeSkill(name) {
    if (!profile) return;
    profile.skills = profile.skills.filter((s) => s !== name);
    saveProfile();
    scheduleExpand();
    markStale();
    renderProfile();
  }

  function scheduleExpand() {
    clearTimeout(expandTimer);
    expandTimer = setTimeout(async () => {
      if (!profile || !profile.skills.length) return;
      try {
        const out = await global.HireLoopAPI.parseResume({ skills: profile.skills });
        profile.inferred = out.inferred || [];
        saveProfile();
        renderProfile();
      } catch (_) {}
    }, 300);
  }

  function render() {
    renderUpload();
    renderProfile();
  }

  function init() {
    loadStored();
    buildShell();
    render();
  }

  function onTabShow() {
    // Prefetch PDF.js when Matches is opened (lazy; not on Browse)
    ensurePdfJs().catch(function () {});
  }

  function getMatchPayload(offset) {
    savePrefs();
    const p = prefs || {};
    const companies = (p.companies || "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const skills = ((profile && profile.skills) || []).join(", ");
    const args = {
      skills,
      target_role: p.target_role || null,
      location: p.location || null,
      remote_ok: p.remote_ok !== false,
      salary_min: p.salary_min ? Number(p.salary_min) : null,
      experience_years:
        levelToYears(p.experience_level) ||
        (profile && profile.experience_years) ||
        null,
      seniority: p.seniority || null,
      visa_needed: !!p.visa_needed,
      companies: companies.length ? companies.join(",") : null,
      posted_within_hours: p.posted_within_hours
        ? Number(p.posted_within_hours)
        : null,
      limit: matchPage.pageSize,
      offset: offset || 0,
      detail: "full",
    };
    // Drop nulls so MCP schema stays clean
    Object.keys(args).forEach((k) => {
      if (args[k] === null || args[k] === "") delete args[k];
    });
    return args;
  }

  function clearStale() {
    stale = false;
    const btn = $("#find-matches");
    if (btn) btn.classList.remove("pulse");
  }

  const LOAD_MSGS = [
    "Finding matches…",
    "Expanding skills through knowledge graph…",
    "Scoring candidates…",
  ];

  function formatNextPoll(iso) {
    if (!iso) return "the next scheduled refresh";
    const t = new Date(iso).getTime();
    if (Number.isNaN(t)) return "the next scheduled refresh";
    const mins = Math.max(0, Math.round((t - Date.now()) / 60000));
    const when = new Date(iso).toLocaleString();
    if (mins <= 0) return `any moment (scheduled ${when})`;
    if (mins < 60) return `${mins} min (scheduled ${when})`;
    const hrs = Math.floor(mins / 60);
    const rem = mins % 60;
    return `${hrs}h ${rem}m (scheduled ${when})`;
  }

  async function refreshNextPoll() {
    try {
      const h = await global.HireLoopAPI.getHealth();
      matchPage.nextPoll =
        (h.data && h.data.next_poll) || (h.next_poll) || null;
    } catch (_) {
      matchPage.nextPoll = null;
    }
  }

  async function runMatch(offset) {
    if (!profile || !profile.skills || !profile.skills.length) {
      if (window.HireLoopUI) {
        window.HireLoopUI.showError("Add at least one skill before matching.");
      }
      return;
    }
    const box = $("#matches-results");
    if (!box) return;
    clearStale();
    matchPage.offset = offset || 0;
    let i = 0;
    box.innerHTML = `<div class="placeholder-panel" id="match-loading">${LOAD_MSGS[0]}</div>`;
    const timer = setInterval(() => {
      i = (i + 1) % LOAD_MSGS.length;
      const el = $("#match-loading");
      if (el) el.textContent = LOAD_MSGS[i];
    }, 500);
    try {
      if (window.HireLoopUI) window.HireLoopUI.clearError();
      if (!global.HireLoopMCP) throw new Error("MCP client not loaded");
      const payload = getMatchPayload(matchPage.offset);
      const data = await global.HireLoopMCP.callTool("match_jobs", payload);
      await refreshNextPoll();
      clearInterval(timer);
      matchPage.total = data.total_matches || 0;
      matchPage.lastData = data;
      renderMatchResults(data);
    } catch (e) {
      clearInterval(timer);
      box.innerHTML = "";
      if (window.HireLoopUI) {
        window.HireLoopUI.showError(
          (e.data && e.data.detail) ||
            e.message ||
            "Matching failed. Check that Neo4j is running."
        );
      }
    }
  }

  function scoreClass(n) {
    if (n >= 75) return "score-high";
    if (n >= 50) return "score-mid";
    return "score-low";
  }

  function splitMissing(job, missing) {
    const req = new Set((job.skills_required || []).map((s) => s.toLowerCase()));
    const nice = new Set((job.skills_nice_to_have || []).map((s) => s.toLowerCase()));
    const missingReq = [];
    const missingNice = [];
    (missing || []).forEach((s) => {
      const k = s.toLowerCase();
      if (nice.has(k) && !req.has(k)) missingNice.push(s);
      else missingReq.push(s);
    });
    return { missingReq, missingNice };
  }

  function renderMatchResults(data) {
    const box = $("#matches-results");
    if (!box) return;
    const matches = data.matches || [];
    const yp = data.your_profile || {};
    const directN = (yp.direct_count != null
      ? yp.direct_count
      : (yp.direct_skills || yp.direct || []).length) || (profile.skills || []).length;
    const inferredN =
      yp.inferred_count != null
        ? yp.inferred_count
        : (yp.inferred_skills || yp.inferred || profile.inferred || []).length;
    const total = data.total_matches || matches.length;
    matchPage.total = total;
    if (!matches.length && matchPage.offset === 0) {
      box.innerHTML = `<div class="placeholder-panel">
        <p>No matches found with your current preferences. Try:</p>
        <ul style="text-align:left;display:inline-block">
          <li>Lowering your salary minimum</li>
          <li>Adding more locations or enabling remote</li>
          <li>Removing company restrictions</li>
        </ul>
      </div>`;
      return;
    }
    const from = total === 0 ? 0 : matchPage.offset + 1;
    const to = matchPage.offset + matches.length;
    const pages = Math.max(1, Math.ceil(total / matchPage.pageSize));
    const page = Math.floor(matchPage.offset / matchPage.pageSize) + 1;
    const onLast = page >= pages;
    const applyHtml = (job) =>
      global.HireLoopUI && global.HireLoopUI.applyControlHtml
        ? global.HireLoopUI.applyControlHtml(job)
        : "";

    let html = `<div class="card match-summary">
      <strong>${total} matches found</strong> · Showing ${from}-${to}<br/>
      <span class="muted">Your skills: ${directN} direct + ${inferredN} inferred</span>
    </div>`;
    matches.forEach((m, idx) => {
      const job = m.job || {};
      const score = m.score || {};
      const overall = score.overall || 0;
      const skillsFit = score.skills_fit || 0;
      const matched = score.matched_skills || (m.skills_analysis && m.skills_analysis.matched) || [];
      const missing = score.missing_skills || (m.skills_analysis && m.skills_analysis.missing) || [];
      const { missingReq, missingNice } = splitMissing(job, missing);
      const matchedHtml = matched
        .map((s) => {
          const name = typeof s === "string" ? s : s.skill;
          const inferred =
            typeof s === "object" && s.match_type && s.match_type !== "direct"
              ? ' <span class="muted">(inferred)</span>'
              : "";
          return `<span class="tag tag-match">✓ ${escape(name)}${inferred}</span>`;
        })
        .join("");
      const missHtml = missing
        .map((s) => `<span class="tag tag-miss">✗ ${escape(s)}</span>`)
        .join("");
      html += `<article class="job-card card match-card" data-idx="${idx}">
        <div class="match-card-top">
          <div class="score-circle ${scoreClass(overall)}">${overall}</div>
          <div class="match-card-main">
            <div class="job-card-top">
              <button type="button" class="job-title-btn" data-expand="${idx}">${escape(job.title || "")}</button>
              ${job.salary_range ? `<span class="job-salary">${escape(job.salary_range)}</span>` : ""}
            </div>
            <div class="job-sub">
              <button type="button" class="company-link" data-company="${escape(job.company || "")}">${escape(job.company || "")}</button>
              ${job.location ? " · " + escape(job.location) : ""}
              ${job.remote_policy ? " · " + escape(job.remote_policy) : ""}
            </div>
            <div class="skills-bar-row">
              <span>Skills match:</span>
              <div class="skills-bar"><div style="width:${skillsFit}%"></div></div>
              <span>${skillsFit}%</span>
            </div>
            <div class="job-skills">${matchedHtml}${missHtml}</div>
            <div class="job-meta muted">${[job.experience, job.employment_type].filter(Boolean).join(" · ")}</div>
            <div class="job-fresh muted">${escape(job.freshness || "")}</div>
            <div class="job-actions">${applyHtml(job)}</div>
          </div>
        </div>
        <div class="job-expand match-expand" data-expand-body="${idx}" hidden></div>
      </article>`;
    });
    const gaps = data.skill_gaps || [];
    if (gaps.length && page === 1) {
      html += `<h3 style="margin-top:24px">Your Skill Gaps</h3>`;
      gaps.forEach((g) => {
        const pct = Math.round((g.frequency || 0) * 100);
        const close = (g.learn_path || []).join(", ");
        html += `<div class="card gap-card">
          <strong>${escape(g.skill)}</strong>
          <p class="muted">Missing in ${pct}% of your matches</p>
          <p>Importance: ${escape(g.importance || "common")}</p>
          ${close ? `<p>You're close: ${escape(close)}</p>` : ""}
        </div>`;
      });
    }
    html += `<div class="pagination" id="match-pagination">
      <button type="button" class="btn btn-secondary" id="match-prev" ${page <= 1 ? "disabled" : ""}>← Previous</button>
      <span>Page ${page} of ${pages}</span>
      <button type="button" class="btn btn-secondary" id="match-next" ${onLast ? "disabled" : ""}>Next →</button>
    </div>`;
    if (onLast) {
      html += `<div class="placeholder-panel match-done" style="margin-top:16px">
        <p><strong>You're done</strong> — you've reviewed all ${total.toLocaleString()} matches for these filters.</p>
        <p class="muted">We'll look for fresh jobs after the next poll — in ${formatNextPoll(matchPage.nextPoll)}.</p>
      </div>`;
    }
    box.innerHTML = html;
    const prev = $("#match-prev");
    const next = $("#match-next");
    if (prev)
      prev.addEventListener("click", () =>
        runMatch(Math.max(0, matchPage.offset - matchPage.pageSize))
      );
    if (next)
      next.addEventListener("click", () =>
        runMatch(matchPage.offset + matchPage.pageSize)
      );
    box.querySelectorAll("[data-expand]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const idx = Number(btn.getAttribute("data-expand"));
        toggleMatchExpand(box, matches[idx], idx, data.skill_gaps || []);
      });
    });
    box.querySelectorAll(".company-link").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (global.HireLoopApp && global.HireLoopApp.showCompany) {
          global.HireLoopApp.showCompany(btn.getAttribute("data-company"));
        }
      });
    });
  }

  function bar(label, pct) {
    const cls = scoreClass(pct);
    return `<div class="breakdown-row ${cls}">
      <span>${label}</span>
      <div class="skills-bar"><div style="width:${pct}%"></div></div>
      <span>${pct}%</span>
    </div>`;
  }

  function toggleMatchExpand(box, m, idx, gaps) {
    const body = box.querySelector(`[data-expand-body="${idx}"]`);
    if (!body) return;
    if (!body.hidden) {
      body.hidden = true;
      return;
    }
    box.querySelectorAll(".match-expand").forEach((n) => (n.hidden = true));
    const job = m.job || {};
    const score = m.score || {};
    const matched = score.matched_skills || [];
    const direct = matched.filter((s) => !s.match_type || s.match_type === "direct");
    const inferred = matched.filter((s) => s.match_type && s.match_type !== "direct");
    const { missingReq, missingNice } = splitMissing(job, score.missing_skills || []);
    let insight = "";
    if (gaps[0] && gaps[0].learn_path && gaps[0].learn_path.length) {
      insight = `<p class="gap-insight">${escape(gaps[0].skill)} is a frequent gap.
        You know ${escape(gaps[0].learn_path.join(", "))} — related foundations.</p>`;
    }
    body.innerHTML = `
      ${bar("Skills fit", score.skills_fit || 0)}
      ${bar("Role fit", score.role_fit || 0)}
      ${bar("Preference fit", score.preference_fit || 0)}
      ${bar("Freshness", score.freshness || 0)}
      ${bar("Overall", score.overall || 0)}
      <p><strong>Matched (direct):</strong> ${direct.map((s) => escape(s.skill || s)).join(", ") || "—"}</p>
      <p><strong>Matched (inferred):</strong> ${inferred.map((s) => escape(s.skill || s)).join(", ") || "—"}</p>
      <p><strong>Missing (required):</strong> ${missingReq.map(escape).join(", ") || "—"}</p>
      <p><strong>Missing (nice):</strong> ${missingNice.map(escape).join(", ") || "—"}</p>
      ${insight}
      <button type="button" class="link-btn" data-collapse>Collapse</button>
    `;
    body.hidden = false;
    body.querySelector("[data-collapse]").addEventListener("click", () => {
      body.hidden = true;
    });
  }

  global.HireLoopMatches = {
    init,
    onTabShow,
    getMatchPayload,
    clearStale,
    hasProfile: () => !!(profile && profile.skills && profile.skills.length),
    runMatch,
  };
})(window);
