// Eligibility GUI. All output uses textContent (never innerHTML) to prevent XSS.
"use strict";
let accessToken = null;   // kept in memory only, not localStorage
let lastBallotToken = null;
const $ = (id) => document.getElementById(id);

function show(ok, title, data) {
  const b = $("banner");
  b.textContent = title;
  b.className = "banner " + (ok ? "ok" : "bad");
  $("out").textContent = JSON.stringify(data, null, 2);
}

async function call(method, url, body) {
  const headers = { "Content-Type": "application/json" };
  if (accessToken) headers.Authorization = "Bearer " + accessToken;
  const res = await fetch(url, { method, headers, body: body ? JSON.stringify(body) : undefined,
                                 credentials: "same-origin" });
  let data = null;
  try { data = await res.json(); } catch { data = {}; }
  return { ok: res.ok, status: res.status, data };
}

async function run(label, method, url, body, okText) {
  const r = await call(method, url, body);
  const detail = r.data && r.data.detail;
  show(r.ok, r.ok ? (okText ? okText(r.data) : label + " – OK") :
       `${label} – HTTP ${r.status}: ${typeof detail === "string" ? detail : "rejected"}`, r.data);
  return r;
}

$("btnLogin").onclick = async () => {
  const role = $("role").value;
  const body = { user_id: $("userId").value.trim(), role };
  if (role === "voter") body.voter_id = $("loginVoter").value.trim();
  accessToken = null;
  const r = await run("Sign in", "POST", "/dev/mock-token", body, () => "Signed in");
  if (r.ok) {
    accessToken = r.data.access_token;
    $("who").textContent = `Signed in as ${body.user_id} (${role}${body.voter_id ? ", " + body.voter_id : ""})`;
    $("out").textContent = "{ \"access_token\": \"[hidden]\" }";
  }
};

$("btnStatus").onclick = () => run("Enrolment status", "GET",
  "/eligibility/status/" + encodeURIComponent($("voterId").value.trim()), null,
  (d) => `Enrolment: ${d.enrolment_status}`);

$("btnCheck").onclick = async () => {
  const r = await call("POST", "/eligibility/check", { voter_id: $("voterId").value.trim() });
  if (r.ok) show(r.data.eligible, r.data.eligible ? "ELIGIBLE to vote" : "NOT eligible – " + r.data.reason, r.data);
  else show(false, `Check – HTTP ${r.status}: ${typeof r.data.detail === "string" ? r.data.detail : "rejected"}`, r.data);
};

$("btnAuthorise").onclick = async () => {
  const r = await run("Authorise", "POST", "/eligibility/authorizations",
    { voter_id: $("voterId").value.trim(), channel: $("channel").value },
    () => "Ballot token issued – voter now marked as voted");
  if (r.ok) lastBallotToken = r.data.ballot_token;
};

$("btnRedeem").onclick = () => {
  if (!lastBallotToken) return show(false, "No ballot token issued in this session yet", {});
  return run("Redeem", "POST", "/eligibility/authorizations/redeem", { ballot_token: lastBallotToken },
    () => "Token accepted (single use)");
};

$("btnEnrol").onclick = () => run("Enrol", "POST", "/eligibility/enrol", {
  voter_id: $("enVoter").value.trim(), full_name: $("enName").value.trim(), date_of_birth: $("enDob").value,
  citizenship: "AU", state: $("enState").value, division: $("enDivision").value.trim(),
  address: $("enAddress").value.trim() }, (d) => `Enrolment ${d.enrolment_status}`);

$("btnApprove").onclick = () => run("Approve", "POST",
  "/eligibility/enrolments/" + encodeURIComponent($("enVoter").value.trim()) + "/approve");

$("btnAddress").onclick = () => run("Update address", "PATCH",
  "/eligibility/electors/" + encodeURIComponent($("enVoter").value.trim()) + "/address",
  { address: $("enAddress").value.trim(), division: $("enDivision").value.trim() });

$("btnVerify").onclick = async () => {
  const r = await call("GET", "/eligibility/audit/verify");
  if (r.ok) show(r.data.valid, r.data.valid ? `Audit chain intact (${r.data.entries} entries)` :
                 `Audit chain BROKEN at entry ${r.data.broken_at_seq}`, r.data);
  else show(false, `Audit – HTTP ${r.status}`, r.data);
};

$("btnRecent").onclick = () => run("Recent audit", "GET", "/eligibility/audit/recent");
