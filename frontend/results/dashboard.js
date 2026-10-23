"use strict";
const el = (id) => document.getElementById(id);
const status = (id, message, isError = false) => {
  const node = el(id);
  node.textContent = message;
  node.classList.toggle("error", isError);
};
const electionId = () => el("election").value.trim();
const pathId = () => encodeURIComponent(electionId());

async function request(path, options = {}) {
  const response = await fetch(path, { cache: "no-store", ...options });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = typeof payload.detail === "string" ? payload.detail : `HTTP ${response.status}`;
    throw new Error(`${response.status}: ${message}`);
  }
  return payload;
}
function addRow(parent, candidate, votes, total) {
  const row = document.createElement("div"); row.className = "bar-row";
  const name = document.createElement("span"); name.textContent = candidate;
  const track = document.createElement("div"); track.className = "bar-track";
  const bar = document.createElement("div"); bar.className = "bar";
  const value = Number(votes);
  bar.style.width = `${total > 0 && Number.isFinite(value) ? Math.max(0, Math.min(100, (value / total) * 100)) : 0}%`;
  track.append(bar);
  const count = document.createElement("strong"); count.textContent = String(votes);
  row.append(name, track, count); parent.append(row);
}
function showResult(data) {
  const names = new Map((data.candidates || []).map(candidate => [candidate.candidate_id, `${candidate.name} — ${candidate.party}`]));
  el("winner").textContent = names.get(data.winner_id) || data.winner_id || "Undetermined";
  el("ballots").textContent = String(data.total_ballots ?? "—");
  el("published").textContent = data.published_at || "—";
  const root = el("rounds"); root.replaceChildren();
  for (const round of (Array.isArray(data.rounds) ? data.rounds : [])) {
    const section = document.createElement("section"); section.className = "round";
    const title = document.createElement("h4"); title.textContent = `Round ${round.round}`; section.append(title);
    const totals = round.totals && typeof round.totals === "object" ? round.totals : {};
    const votes = Object.values(totals).reduce((acc, value) => acc + (Number(value) || 0), 0);
    for (const [candidate, amount] of Object.entries(totals)) addRow(section, names.get(candidate) || candidate, amount, votes);
    if (round.eliminated) {
      const removed = document.createElement("p"); removed.textContent = `Excluded: ${names.get(round.eliminated) || round.eliminated}`; section.append(removed);
    }
    root.append(section);
  }
  el("public-result").hidden = false;
}
async function loadPublished(event) {
  if (event) event.preventDefault();
  el("public-result").hidden = true;
  if (!electionId()) return status("public-message", "Enter an election ID", true);
  try {
    const data = await request(`/results/${pathId()}`);
    showResult(data);
    status("public-message", "Published result loaded successfully.");
  } catch (error) {
    status("public-message", `Cannot load published result: ${error.message}`, true);
  }
}
let adminToken = null;
let busy = false;
function controls() {
  for (const action of ["count", "publish", "verify", "events"]) {
    el(`${action}-button`).disabled = busy || !adminToken;
  }
  el("login-button").disabled = busy;
  el("logout-button").disabled = busy;
  el("logout-button").hidden = !adminToken;
  el("admin-login").hidden = Boolean(adminToken);
}
function clearSession() {
  adminToken = null;
  el("admin-identity").textContent = "Logged out.";
  el("admin-output").textContent = "";
  el("admin-output").hidden = true;
  controls();
}
async function protectedRequest(path, options = {}) {
  const response = await fetch(path, {cache: "no-store", ...options,
    headers: {...(options.headers || {}), Authorization: `Bearer ${adminToken}`}});
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401) clearSession();
    throw new Error(typeof data.detail === "string" ? data.detail : `HTTP ${response.status}`);
  }
  return data;
}
async function administratorAction(action) {
  if (busy || !adminToken) return;
  if (!electionId()) return status("admin-message", "Enter an election ID first.", true);
  const paths = {
    count: ["/results/count", "POST"],
    publish: [`/results/${pathId()}/publish`, "POST"],
    verify: [`/results/${pathId()}/audit/verify`, "GET"],
    events: [`/results/${pathId()}/audit`, "GET"]
  };
  const [path, method] = paths[action];
  busy = true;
  controls();
  const output = el("admin-output"); output.hidden = true;
  try {
    // /count uses the server's configured election, never a caller-selected fixture.
    if (action === "count") {
      const catalog = await request("/ballots/candidates");
      if (catalog.election_id !== electionId()) throw new Error("Use the configured election ID shown above.");
    }
    const data = await protectedRequest(path, {method});
    output.textContent = JSON.stringify(data, null, 2); output.hidden = false;
    status("admin-message", `${action} succeeded.`);
    if (action === "publish") await loadPublished();
  } catch (error) {
    status("admin-message", `${action} failed: ${error.message}`, true);
  } finally {
    busy = false;
    controls();
  }
}
el("admin-login").addEventListener("submit", async event => {
  event.preventDefault();
  if (busy) return;
  busy = true;
  clearSession();
  try {
    const credentials = {username: el("admin-username").value.trim(), password: el("admin-password").value};
    if (el("admin-mfa").value.trim()) credentials.mfa_code = el("admin-mfa").value.trim();
    const session = await request("/auth/login", {method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify(credentials)});
    adminToken = session.access_token;
    const identity = await protectedRequest("/auth/verify");
    if (identity.role !== "admin") {
      await protectedRequest("/auth/logout", {method:"POST"});
      throw new Error("This account is not a results administrator.");
    }
    el("admin-identity").textContent = `Logged in as ${identity.username} (administrator).`;
    status("admin-message", "Administrator login successful. Count only after the election is closed.");
  } catch (error) {
    clearSession();
    status("admin-message", error.message, true);
  } finally {
    el("admin-password").value = "";
    el("admin-mfa").value = "";
    busy = false;
    controls();
  }
});
el("logout-button").addEventListener("click", async () => {
  if (busy) return;
  busy = true;
  controls();
  try {
    await protectedRequest("/auth/logout", {method:"POST"});
    status("admin-message", "Logged out.");
  } catch (error) {
    status("admin-message", `Local session cleared. ${error.message}`, true);
  } finally {
    clearSession();
    busy = false;
    controls();
  }
});
el("lookup-form").addEventListener("submit", loadPublished);
for (const action of ["count", "publish", "verify", "events"]) {
  el(`${action}-button`).addEventListener("click", () => administratorAction(action));
}
async function loadElectionState() {
  try {
    const catalog = await request("/ballots/candidates");
    el("election").value = catalog.election_id;
    status("election-state", `${catalog.election_id} — ${catalog.status}. Only accepted ballots from this election are counted.`);
  } catch (error) {
    status("election-state", `Election state unavailable: ${error.message}`, true);
  }
}
controls();
loadElectionState();
