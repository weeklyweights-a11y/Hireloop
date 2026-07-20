/* API client — fetch wrapper */
(function (global) {
  const DEFAULT_TIMEOUT_MS = 30000;

  async function request(path, options = {}) {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), options.timeoutMs || DEFAULT_TIMEOUT_MS);
    try {
      const res = await fetch(path, {
        ...options,
        signal: ctrl.signal,
        headers: {
          Accept: "application/json",
          ...(options.body ? { "Content-Type": "application/json" } : {}),
          ...options.headers,
        },
      });
      const text = await res.text();
      let data = null;
      try {
        data = text ? JSON.parse(text) : null;
      } catch {
        data = { detail: text };
      }
      if (!res.ok) {
        const err = new Error((data && (data.detail || data.error)) || res.statusText);
        err.status = res.status;
        err.data = data;
        throw err;
      }
      return data;
    } finally {
      clearTimeout(t);
    }
  }

  global.HireLoopAPI = {
    getStats: () => request("/stats"),
    getHealth: () => request("/health"),
    searchJobs: (params) => {
      const q = new URLSearchParams();
      Object.entries(params || {}).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== "") q.set(k, String(v));
      });
      return request("/jobs/search?" + q.toString());
    },
    getJob: (id) => request("/jobs/" + encodeURIComponent(id)),
    metaLocations: (q) =>
      request("/meta/locations?q=" + encodeURIComponent(q || "")),
    metaRoles: (q) => request("/meta/roles?q=" + encodeURIComponent(q || "")),
    parseResume: (body) =>
      request("/resume/parse", { method: "POST", body: JSON.stringify(body) }),
    matchJobs: (body) =>
      request("/jobs/match", { method: "POST", body: JSON.stringify(body) }),
    companyJobs: (company, params) => {
      const q = new URLSearchParams(params || {});
      return request(
        "/jobs/companies/" + encodeURIComponent(company) + "?" + q.toString()
      );
    },
    companyInsights: (company) =>
      request("/jobs/companies/" + encodeURIComponent(company) + "/insights"),
  };
})(window);
