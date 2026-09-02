/* Shared front-end runtime.
 *
 * One API client, one toast system, one table renderer. Pages describe what
 * they need; none of them re-implement fetch, error handling or token refresh.
 */

(function (global) {
  "use strict";

  /* ---------------- API client ---------------- */

  const API = {
    get access() { return localStorage.getItem("access"); },
    get refresh() { return localStorage.getItem("refresh"); },
    get user() {
      try { return JSON.parse(localStorage.getItem("user") || "null"); }
      catch (e) { return null; }
    },

    setSession(data) {
      if (data.access) localStorage.setItem("access", data.access);
      if (data.refresh) localStorage.setItem("refresh", data.refresh);
      if (data.user) localStorage.setItem("user", JSON.stringify(data.user));
    },

    clear() {
      ["access", "refresh", "user"].forEach((k) => localStorage.removeItem(k));
    },

    async request(path, options = {}, allowRetry = true) {
      const opts = Object.assign({}, options);
      opts.headers = Object.assign({}, options.headers);

      if (opts.body !== undefined && !(opts.body instanceof FormData)) {
        opts.headers["Content-Type"] = "application/json";
        if (typeof opts.body !== "string") opts.body = JSON.stringify(opts.body);
      }
      if (this.access) opts.headers["Authorization"] = "Bearer " + this.access;

      let response;
      try {
        response = await fetch(path, opts);
      } catch (err) {
        // Network failure is different from a rejected request, and the user
        // needs to know it is their connection rather than their input.
        throw new APIError("Could not reach the server. Check your connection.", 0, {});
      }

      // An expired access token is normal, not an error: swap it silently.
      if (response.status === 401 && allowRetry && this.refresh) {
        const refreshed = await fetch("/api/token/refresh/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh: this.refresh }),
        });
        if (refreshed.ok) {
          this.setSession(await refreshed.json());
          return this.request(path, options, false);
        }
        this.clear();
        redirectToLogin();
        throw new APIError("Your session has expired.", 401, {});
      }

      if (!response.ok) {
        let payload = {};
        try { payload = await response.json(); } catch (e) { /* not JSON */ }
        throw new APIError(messageFor(response.status, payload), response.status, payload);
      }

      if (response.status === 204) return null;
      const type = response.headers.get("Content-Type") || "";
      return type.includes("json") ? response.json() : response;
    },

    get(path) { return this.request(path); },
    post(path, body) { return this.request(path, { method: "POST", body }); },
    patch(path, body) { return this.request(path, { method: "PATCH", body }); },
    del(path) { return this.request(path, { method: "DELETE" }); },

    /* Lists arrive paginated or plain depending on the endpoint. */
    rowsOf(payload) {
      if (Array.isArray(payload)) return payload;
      return (payload && payload.results) || [];
    },
    countOf(payload) {
      if (Array.isArray(payload)) return payload.length;
      return (payload && payload.count) || 0;
    },
  };

  class APIError extends Error {
    constructor(message, status, payload) {
      super(message);
      this.status = status;
      this.payload = payload || {};
    }
    /* Field errors, so a form can show them next to the offending input. */
    get fieldErrors() {
      const out = {};
      Object.entries(this.payload).forEach(([key, value]) => {
        if (key === "detail" || key === "error") return;
        out[key] = Array.isArray(value) ? value.join(" ") : String(value);
      });
      return out;
    }
  }

  function messageFor(status, payload) {
    if (payload && payload.detail) return payload.detail;
    if (payload && payload.error) return payload.error;
    if (status === 403) return "You do not have permission to do that.";
    if (status === 404) return "Not found.";
    if (status === 400) return "Please check the highlighted fields.";
    if (status >= 500) return "Something went wrong on the server.";
    return "Request failed.";
  }

  /* ---------------- Toasts ---------------- */

  function toast(message, kind = "ok", timeout = 4500) {
    let host = document.querySelector(".toasts");
    if (!host) {
      host = document.createElement("div");
      host.className = "toasts";
      // Announced to screen readers without stealing focus.
      host.setAttribute("role", "status");
      host.setAttribute("aria-live", "polite");
      document.body.appendChild(host);
    }

    const el = document.createElement("div");
    el.className = "toast toast--" + kind;
    el.innerHTML =
      '<div style="flex:1">' + escapeHTML(message) + "</div>" +
      '<button class="toast__close" aria-label="Dismiss">&times;</button>';
    el.querySelector("button").onclick = () => el.remove();

    host.appendChild(el);
    if (timeout) setTimeout(() => el.remove(), timeout);
  }

  /* ---------------- Rendering helpers ---------------- */

  function escapeHTML(value) {
    if (value === null || value === undefined) return "";
    return String(value).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  /* Every value that reaches the DOM goes through escapeHTML. Student names
   * and remarks are user input, so interpolating them raw would be an XSS. */
  function td(value, className) {
    return "<td" + (className ? ' class="' + className + '"' : "") + ">" +
      escapeHTML(value) + "</td>";
  }

  function pill(text, kind) {
    return '<span class="pill pill--' + kind + '">' + escapeHTML(text) + "</span>";
  }

  const STATUS_TONE = {
    PRESENT: "ok", SUCCESS: "ok", Active: "ok", COMPLETED: "ok", SENT: "ok",
    LATE: "warn", PENDING: "warn", IN_PROGRESS: "warn",
    ABSENT: "danger", FAILED: "danger",
  };
  function statusPill(value) {
    if (!value) return "";
    const label = String(value).replace(/_/g, " ").toLowerCase();
    return '<span class="pill pill--' + (STATUS_TONE[value] || "muted") + '">' +
      escapeHTML(label.charAt(0).toUpperCase() + label.slice(1)) + "</span>";
  }

  function skeletonRows(columns, rows = 5) {
    let html = "";
    for (let r = 0; r < rows; r++) {
      html += "<tr>";
      for (let c = 0; c < columns; c++) html += '<td><div class="skeleton"></div></td>';
      html += "</tr>";
    }
    return html;
  }

  function emptyRow(columns, title, hint) {
    return '<tr><td colspan="' + columns + '"><div class="empty">' +
      '<div class="empty__title">' + escapeHTML(title) + "</div>" +
      (hint ? "<div>" + escapeHTML(hint) + "</div>" : "") +
      "</div></td></tr>";
  }

  function money(value) {
    const number = Number(value || 0);
    // Indian digit grouping: 1,50,000 rather than 150,000.
    return "₹" + number.toLocaleString("en-IN", { minimumFractionDigits: 2,
      maximumFractionDigits: 2 });
  }

  function formatDate(value) {
    if (!value) return "—";
    const d = new Date(value);
    if (isNaN(d)) return value;
    return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
  }

  function formatDateTime(value) {
    if (!value) return "—";
    const d = new Date(value);
    if (isNaN(d)) return value;
    return d.toLocaleString("en-IN", { day: "2-digit", month: "short",
      hour: "2-digit", minute: "2-digit" });
  }

  /* Debounce keystrokes so a search box does not fire a request per letter. */
  function debounce(fn, wait = 300) {
    let timer;
    return function (...args) {
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, args), wait);
    };
  }

  /* ---------------- Forms ---------------- */

  function readForm(form) {
    const data = {};
    new FormData(form).forEach((value, key) => {
      if (value !== "") data[key] = value;
    });
    return data;
  }

  function clearFormErrors(form) {
    form.querySelectorAll(".field__error").forEach((el) => el.remove());
    form.querySelectorAll("[aria-invalid]").forEach((el) => {
      el.removeAttribute("aria-invalid");
    });
  }

  function showFormErrors(form, error) {
    clearFormErrors(form);
    const fields = error.fieldErrors || {};
    let firstBad = null;

    Object.entries(fields).forEach(([name, message]) => {
      const input = form.querySelector('[name="' + name + '"]');
      if (!input) return;
      input.setAttribute("aria-invalid", "true");
      const note = document.createElement("div");
      note.className = "field__error";
      note.textContent = message;
      input.insertAdjacentElement("afterend", note);
      if (!firstBad) firstBad = input;
    });

    // Errors with no matching field would otherwise vanish silently.
    const unmatched = Object.keys(fields).filter(
      (name) => !form.querySelector('[name="' + name + '"]')
    );
    if (!Object.keys(fields).length || unmatched.length) {
      toast(unmatched.map((k) => fields[k]).join(" ") || error.message, "danger");
    }
    if (firstBad) firstBad.focus();
  }

  async function submitting(button, work) {
    const original = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<span class="spinner"></span> Saving';
    try { return await work(); }
    finally { button.disabled = false; button.innerHTML = original; }
  }

  /* ---------------- Session ---------------- */

  function redirectToLogin() {
    const here = window.location.pathname + window.location.search;
    window.location = "/login/?next=" + encodeURIComponent(here);
  }

  const ADMIN_ROLES = ["SUPER_ADMIN", "ORGANIZATION_ADMIN"];
  const Session = {
    get user() { return API.user; },
    get role() { return (API.user || {}).role; },
    isAdmin() { return ADMIN_ROLES.includes(this.role); },
    isStaff() { return this.isAdmin() || this.role === "TEACHER"; },
    can(...roles) { return roles.includes(this.role); },
  };

  global.API = API;
  global.APIError = APIError;
  global.Session = Session;
  global.UI = {
    toast, escapeHTML, td, pill, statusPill, skeletonRows, emptyRow,
    money, formatDate, formatDateTime, debounce,
    readForm, showFormErrors, clearFormErrors, submitting, redirectToLogin,
  };
})(window);

/* ---------------- Tenant branding ----------------
 *
 * One deployment serves many institutions. Colours, logo and wording come from
 * the signed-in user's organization, cached in localStorage so navigation does
 * not flash the default theme, and refreshed in the background so a change
 * takes effect without anyone signing out.
 */

(function (global) {
  "use strict";

  const NEUTRAL = {
    organization: "Institution", faculty: "Faculty", faculty_plural: "Faculty",
    class_group: "Class", class_group_plural: "Classes",
    guardian: "Guardian", guardian_plural: "Guardians",
    admission_no: "Admission no.", campus: "Campus",
  };

  function cached() {
    try { return JSON.parse(localStorage.getItem("brand") || "null"); }
    catch (e) { return null; }
  }

  /* Readable text on top of an arbitrary client colour. A tenant that picks a
   * pale yellow would otherwise get white-on-yellow navigation. */
  function contrastInk(hex) {
    const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex || "");
    if (!m) return "#ffffff";
    const [r, g, b] = [1, 2, 3].map((i) => parseInt(m[i], 16) / 255);
    const lin = (c) => (c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));
    const luminance = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
    return luminance > 0.45 ? "#0f172a" : "#ffffff";
  }

  function apply(brand) {
    if (!brand) return;
    const root = document.documentElement;

    if (brand.primary_color) {
      root.style.setProperty("--brand", brand.primary_color);
      root.style.setProperty("--brand-ink", contrastInk(brand.primary_color));
    }

    const nameEl = document.getElementById("brand-name");
    if (nameEl && brand.organization_name) {
      nameEl.textContent = brand.organization_name;
      nameEl.title = brand.organization_name;
    }

    const mark = document.getElementById("brand-mark");
    if (mark) {
      if (brand.logo_url) {
        mark.innerHTML =
          '<img src="' + UI.escapeHTML(brand.logo_url) + '" alt="" ' +
          'style="width:100%;height:100%;object-fit:contain;border-radius:6px">';
        mark.style.background = "transparent";
      } else {
        mark.textContent = brand.initials || "SS";
      }
    }

    const footer = document.getElementById("brand-footer");
    if (footer) footer.textContent = brand.organization_type || "";

    document.title = document.title.replace(
      /Student Management System$/, brand.organization_name || "Student Management"
    );

    // Swap wording for this tenant: a coaching centre has batches and
    // trainers where a school has classes and teachers.
    const words = brand.vocabulary || NEUTRAL;
    document.querySelectorAll("[data-term]").forEach((el) => {
      const term = words[el.dataset.term];
      if (term) el.textContent = term;
    });
  }

  const Brand = {
    get current() { return cached() || { vocabulary: NEUTRAL }; },

    term(key) {
      const words = (cached() || {}).vocabulary || NEUTRAL;
      return words[key] || NEUTRAL[key] || key;
    },

    async load() {
      apply(cached());          // paint immediately from cache
      try {
        const brand = await API.get("/api/organizations/me/");
        localStorage.setItem("brand", JSON.stringify(brand));
        apply(brand);
      } catch (err) {
        // A user with no organization, or an offline reload: the neutral
        // wording already on screen is a perfectly usable fallback.
      }
    },
  };

  global.Brand = Brand;
})(window);
