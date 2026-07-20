/* Shared UI helpers */
(function (global) {
  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    if (attrs) {
      Object.entries(attrs).forEach(([k, v]) => {
        if (k === "className") node.className = v;
        else if (k === "text") node.textContent = v;
        else if (k === "html") node.innerHTML = v;
        else if (k.startsWith("on") && typeof v === "function")
          node.addEventListener(k.slice(2).toLowerCase(), v);
        else if (v !== false && v != null) node.setAttribute(k, v === true ? "" : v);
      });
    }
    (children || []).forEach((c) => {
      if (c == null) return;
      node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return node;
  }

  function showError(msg) {
    const box = document.getElementById("global-error");
    if (!box) return;
    box.textContent = msg;
    box.classList.add("visible");
  }

  function clearError() {
    const box = document.getElementById("global-error");
    if (!box) return;
    box.textContent = "";
    box.classList.remove("visible");
  }

  function skillTags(skills, limit) {
    const list = skills || [];
    const show = limit ? list.slice(0, limit) : list;
    const more = limit && list.length > limit ? list.length - limit : 0;
    return (
      show.map((s) => `<span class="tag">${escapeHtml(s)}</span>`).join("") +
      (more ? `<span class="tag-more">+${more} more</span>` : "")
    );
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function applyControlHtml(job) {
    if (job && job.apply_url) {
      return `<a class="btn btn-primary btn-sm" href="${escapeHtml(job.apply_url)}" target="_blank" rel="noopener noreferrer">Apply</a>`;
    }
    return `<button type="button" class="btn btn-sm btn-disabled" disabled>No apply link</button>`;
  }

  function renderJobCard(job, opts) {
    opts = opts || {};
    const card = el("article", { className: "job-card card", "data-job-id": job.id });
    const salary = job.salary_range
      ? `<span class="job-salary">${escapeHtml(job.salary_range)}</span>`
      : "";
    const remote =
      job.remote_policy === "remote"
        ? '<span class="remote-pill">Remote</span>'
        : escapeHtml(job.remote_policy || "");
    const loc = [job.location, remote].filter(Boolean).join(" · ");
    const visa =
      job.visa_sponsorship === "sponsors"
        ? '<span class="visa-pill">Sponsors visa</span>'
        : "";
    const meta = [job.experience, visa, job.employment_type].filter(Boolean).join(" · ");
    const posted = job.first_seen
      ? "Posted " + (job.freshness || relativeHint(job.first_seen))
      : "";
    const verified = job.last_verified
      ? "Verified " + (job.freshness || "")
      : "";
    // Prefer API freshness for verified line; posted uses first_seen label when available
    const freshLine = [job.freshness ? "Verified " + job.freshness : "", posted]
      .filter(Boolean)
      .join(" · ");

    card.innerHTML = `
      <div class="job-card-top">
        <button type="button" class="job-title-btn">${escapeHtml(job.title)}</button>
        ${salary}
      </div>
      <div class="job-sub">
        <button type="button" class="company-link" data-company="${escapeHtml(job.company)}">${escapeHtml(job.company)}</button>
        ${loc ? " · " + loc : ""}
      </div>
      <div class="job-skills">${skillTags(job.skills_required, 4)}</div>
      <div class="job-meta muted">${meta}</div>
      <div class="job-fresh muted">${freshLine || escapeHtml(job.freshness || "")}</div>
      <div class="job-actions">
        ${applyControlHtml(job)}
      </div>
      <div class="job-expand" hidden></div>
    `;
    const titleBtn = card.querySelector(".job-title-btn");
    if (titleBtn && opts.onExpand) {
      titleBtn.addEventListener("click", () => opts.onExpand(job.id, card));
    }
    card.addEventListener("click", (e) => {
      if (e.target.closest("a, button, .company-link")) return;
      if (opts.tapExpand && opts.onExpand) opts.onExpand(job.id, card);
    });
    const co = card.querySelector(".company-link");
    if (co && opts.onCompany) {
      co.addEventListener("click", (e) => {
        e.preventDefault();
        opts.onCompany(job.company);
      });
    }
    return card;
  }

  function relativeHint() {
    return "";
  }

  function renderJobDetail(detail) {
    const desc = escapeHtml(detail.description_text || "").replace(/\n/g, "<br>");
    return `
      <div class="job-detail-block">
        <p class="job-desc">${desc || "<span class='muted'>No description.</span>"}</p>
        <p><strong>Required:</strong> ${skillTags(detail.skills_required) || "—"}</p>
        <p><strong>Nice to have:</strong> ${skillTags(detail.skills_nice_to_have) || "—"}</p>
        ${detail.department ? `<p><strong>Department:</strong> ${escapeHtml(detail.department)}</p>` : ""}
        ${detail.apply_url ? `<p><a href="${escapeHtml(detail.apply_url)}" target="_blank" rel="noopener noreferrer">View on company site →</a></p>` : `<p class="muted">No apply link</p>`}
        <button type="button" class="link-btn" data-collapse>Collapse</button>
      </div>
    `;
  }

  global.HireLoopUI = {
    el,
    showError,
    clearError,
    escapeHtml,
    skillTags,
    applyControlHtml,
    renderJobCard,
    renderJobDetail,
  };
})(window);
