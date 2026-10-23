"use strict";

// Each page session holds its token in memory. Refreshing requires sign-in again.
let accessToken = null;
let identity = null;
let busy = false;
const $ = (id) => document.getElementById(id);

function show(ok, title, data = {}) {
  $("banner").textContent = title;
  $("banner").className = "banner " + (ok ? "ok" : "bad");
  $("out").textContent = JSON.stringify(data, null, 2);
}

function updateControls() {
  $("btnLogin").disabled = busy || Boolean(identity);
  $("btnLogout").disabled = busy || !accessToken;
  for (const id of ["username", "password", "mfaCode"]) {
    $(id).disabled = busy || Boolean(identity);
  }
  document.querySelectorAll("[data-protected]").forEach((control) => {
    control.disabled = busy || !identity;
  });
  const officer = identity?.role === "officer";
  $("officerPanel").hidden = !officer;
  $("btnApprove").hidden = !officer;
  $("voterId").readOnly = !officer;
  $("enVoter").readOnly = !officer;
}

function clearSession() {
  accessToken = null;
  identity = null;
  $("who").textContent = "Not signed in.";
  $("voterId").value = "";
  $("enVoter").value = "";
  updateControls();
}

function errorText(response) {
  const detail = response.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return "Check the fields and try again.";
  return "Request rejected.";
}

async function call(method, url, body) {
  const headers = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (accessToken) headers.Authorization = "Bearer " + accessToken;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 12000);
  try {
    const response = await fetch(url, {
      method, headers, signal: controller.signal, cache: "no-store",
      credentials: "same-origin",
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    let data = {};
    try { data = await response.json(); } catch { /* Keep a generic error. */ }
    if (response.status === 401 && accessToken) clearSession();
    return { ok: response.ok, status: response.status, data };
  } finally {
    clearTimeout(timeout);
  }
}

async function operation(label, action) {
  if (busy) return;
  busy = true;
  updateControls();
  try {
    await action();
  } catch {
    show(false, label + " could not finish. Check the server and your connection.");
  } finally {
    busy = false;
    updateControls();
  }
}

async function run(label, method, url, body, success) {
  if (!identity) {
    show(false, "Sign in with your registered account first.");
    return null;
  }
  const response = await call(method, url, body);
  if (!response.ok) {
    show(false, `${label} — HTTP ${response.status}: ${errorText(response)}`);
  } else {
    show(true, success ? success(response.data) : label + " successful.", response.data);
  }
  return response;
}

$("loginForm").addEventListener("submit", (event) => {
  event.preventDefault();
  if (identity) return;
  operation("Sign in", async () => {
    let pendingToken = null;
    try {
      const response = await call("POST", "/auth/login", {
        username: $("username").value.trim(),
        password: $("password").value,
        mfa_code: $("mfaCode").value.trim() || null,
      });
      if (!response.ok) {
        show(false, `Sign in — HTTP ${response.status}: ${errorText(response)}`);
        return;
      }
      if (typeof response.data.access_token !== "string" || !response.data.access_token) {
        show(false, "The login service returned an unexpected response.");
        return;
      }
      accessToken = response.data.access_token;
      pendingToken = accessToken;
      const verification = await call("GET", "/auth/verify");
      if (!verification.ok) {
        show(false, `Session verification — HTTP ${verification.status}: ${errorText(verification)}`);
        return;
      }
      const verified = verification.data;
      if (typeof verified.user_id !== "string" ||
          !["voter", "officer"].includes(verified.role)) {
        show(false, "This account cannot use voter or officer eligibility functions.");
        return;
      }
      if (verified.role === "voter" && !/^V\d{4,9}$/.test(verified.voter_id || "")) {
        show(false, "This account has no electoral-roll link. Contact the demo operator.");
        return;
      }
      identity = verified;
      pendingToken = null;
      $("who").textContent = `Signed in as ${verified.username} (${verified.role})`;
      $("voterId").value = verified.voter_id || "";
      $("enVoter").value = verified.voter_id || "";
      show(true, "Session verified. You can now check enrolment and eligibility.", {
        username: verified.username, role: verified.role, voter_id: verified.voter_id,
      });
    } finally {
      $("password").value = "";
      $("mfaCode").value = "";
      if (pendingToken) {
        accessToken = pendingToken;
        try { await call("POST", "/auth/logout"); } catch { /* Session expires normally. */ }
        clearSession();
      }
    }
  });
});

$("btnLogout").onclick = () => operation("Sign out", async () => {
  try {
    const response = await call("POST", "/auth/logout");
    show(response.ok, response.ok ? "Signed out successfully." :
      "Local session cleared. Server sign-out was not confirmed.");
  } finally {
    clearSession();
  }
});

$("btnStatus").onclick = () => operation("Enrolment status", () => run(
  "Enrolment status", "GET",
  "/eligibility/status/" + encodeURIComponent($("voterId").value.trim()),
  undefined, (data) => `Enrolment: ${data.enrolment_status}`,
));

$("btnCheck").onclick = () => operation("Eligibility check", async () => {
  const response = await run("Eligibility check", "POST", "/eligibility/check",
    { voter_id: $("voterId").value.trim() });
  if (response?.ok) {
    show(response.data.eligible === true, response.data.eligible ?
      "ELIGIBLE to vote. No vote has been recorded." :
      "NOT eligible — " + response.data.reason, response.data);
  }
});

$("btnEnrol").onclick = () => operation("Enrolment", () => run(
  "Enrolment", "POST", "/eligibility/enrol", {
    voter_id: $("enVoter").value.trim(), full_name: $("enName").value.trim(),
    date_of_birth: $("enDob").value, citizenship: "AU", state: $("enState").value,
    division: $("enDivision").value.trim(), address: $("enAddress").value.trim(),
  }, (data) => `Enrolment: ${data.enrolment_status}`,
));

$("btnApprove").onclick = () => operation("Approve enrolment", () => run(
  "Approve enrolment", "POST",
  "/eligibility/enrolments/" + encodeURIComponent($("enVoter").value.trim()) + "/approve",
));

$("btnAddress").onclick = () => operation("Address update", () => run(
  "Address update", "PATCH",
  "/eligibility/electors/" + encodeURIComponent($("enVoter").value.trim()) + "/address",
  { address: $("enAddress").value.trim(), division: $("enDivision").value.trim() },
));

$("btnVerify").onclick = () => operation("Audit verification", async () => {
  const response = await run("Audit verification", "GET", "/eligibility/audit/verify");
  if (response?.ok) show(response.data.valid === true,
    response.data.valid ? "Audit chain intact." : "Audit chain verification failed.", response.data);
});

$("btnRecent").onclick = () => operation("Recent audit", () => run(
  "Recent audit", "GET", "/eligibility/audit/recent",
));

updateControls();
