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
  el("winner").textContent = data.winner_id || "Undetermined";
  el("ballots").textContent = String(data.total_ballots ?? "—");
  el("published").textContent = data.published_at || "—";
  const root = el("rounds"); root.replaceChildren();
  for (const round of (Array.isArray(data.rounds) ? data.rounds : [])) {
    const section = document.createElement("section"); section.className = "round";
    const title = document.createElement("h4"); title.textContent = `Round ${round.round}`; section.append(title);
    const totals = round.totals && typeof round.totals === "object" ? round.totals : {};
    const votes = Object.values(totals).reduce((acc, value) => acc + (Number(value) || 0), 0);
    for (const [candidate, amount] of Object.entries(totals)) addRow(section, candidate, amount, votes);
    if (round.eliminated) {
      const removed = document.createElement("p"); removed.textContent = `Excluded: ${round.eliminated}`; section.append(removed);
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
async function administratorAction(action) {
  if (!electionId()) return status("admin-message", "Enter an election ID first.", true);
  const token = el("admin-token").value;
  if (!token) return status("admin-message", "Enter the local administrator token first.", true);
  const paths = {
    count: ["/results/count", "POST"],
    publish: [`/results/${pathId()}/publish`, "POST"],
    verify: [`/results/${pathId()}/audit/verify`, "GET"],
    events: [`/results/${pathId()}/audit`, "GET"]
  };
  const [path, method] = paths[action];
  const output = el("admin-output"); output.hidden = true;
  try {
    const data = await request(path, {method, headers:{"X-Results-Admin-Token": token}});
    output.textContent = JSON.stringify(data, null, 2); output.hidden = false;
    status("admin-message", `${action} succeeded.`);
    if (action === "publish") await loadPublished();
  } catch(error) {
    status("admin-message", `${action} failed: ${error.message}`, true);
  }
}
el("lookup-form").addEventListener("submit", loadPublished);
for (const action of ["count", "publish", "verify", "events"]) {
  el(`${action}-button`).addEventListener("click", () => administratorAction(action));
}
