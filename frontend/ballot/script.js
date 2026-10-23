"use strict";
(() => {
  const el = id => document.getElementById(id);
  let token = null;
  let identity = null;
  let catalog = null;
  let busy = false;
  let submitted = false;
  let selections = [];

  function updateControls() {
    const ready = Boolean(identity && catalog && catalog.status === "OPEN" &&
      catalog.candidates.length && !busy && !submitted);
    el("choices").disabled = !ready;
    el("confirmVote").disabled = !ready;
    el("submitButton").disabled = !ready;
    el("loginButton").disabled = busy;
    el("refreshButton").disabled = busy;
    el("logoutButton").disabled = busy;
    el("logoutButton").hidden = !token;
  }
  function clearSession() {
    token = null;
    identity = null;
    el("identity").textContent = "Logged out.";
    el("loginForm").hidden = false;
    el("confirmVote").checked = false;
    selections.forEach(item => { item.input.value = ""; });
    updateControls();
  }
  async function request(path, options = {}) {
    const headers = {"Content-Type": "application/json"};
    if (token) headers.Authorization = `Bearer ${token}`;
    const response = await fetch(path, { ...options, headers, cache: "no-store" });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      if (response.status === 401) clearSession();
      throw new Error(typeof data.detail === "string" ? data.detail : `Request failed (${response.status}).`);
    }
    return data;
  }
  async function loadCatalog() {
    catalog = null;
    selections = [];
    el("candidates").replaceChildren();
    el("confirmVote").checked = false;
    updateControls();
    try {
      const data = await request("/ballots/candidates");
      if (!Array.isArray(data.candidates)) throw new Error("Candidate list is unavailable.");
      catalog = data;
      el("election").textContent = `${data.election_id} — ${data.title} — ${data.status}`;
      for (const [index, candidate] of data.candidates.entries()) {
        const row = document.createElement("div");
        row.className = "candidate";
        const label = document.createElement("label");
        const select = document.createElement("select");
        select.id = `preference-${index}`;
        select.required = true;
        label.htmlFor = select.id;
        label.textContent = `${candidate.name} — ${candidate.party}`;
        const placeholder = document.createElement("option");
        placeholder.value = "";
        placeholder.textContent = "Choose rank";
        select.append(placeholder);
        for (let rank = 1; rank <= data.candidates.length; rank++) {
          const option = document.createElement("option");
          option.value = String(rank);
          option.textContent = String(rank);
          select.append(option);
        }
        row.append(label, select);
        el("candidates").append(row);
        selections.push({candidateId: candidate.candidate_id, input: select});
      }
      if (data.status !== "OPEN") el("message").textContent = "The election is not open for voting.";
      else if (!data.candidates.length) el("message").textContent = "No active candidates are available.";
    } catch (error) {
      el("election").textContent = "Election unavailable.";
      el("message").textContent = error.message;
    }
    updateControls();
  }
  el("loginForm").addEventListener("submit", async event => {
    event.preventDefault();
    if (busy) return;
    busy = true;
    clearSession();
    try {
      const credentials = {username: el("username").value.trim(), password: el("password").value};
      if (el("mfa").value.trim()) credentials.mfa_code = el("mfa").value.trim();
      const session = await request("/auth/login", {method: "POST", body: JSON.stringify(credentials)});
      token = session.access_token;
      const verified = await request("/auth/verify");
      if (verified.role !== "voter" || !verified.voter_id) {
        await request("/auth/logout", {method: "POST"});
        clearSession();
        throw new Error("A linked voter account is required. Ask the local operator to check your account.");
      }
      identity = verified;
      submitted = false;
      el("identity").textContent = `Logged in as ${verified.username} (${verified.voter_id}).`;
      el("loginForm").hidden = true;
      el("message").textContent = "Choose your preferences. Eligibility is checked again when you submit.";
    } catch (error) {
      clearSession();
      el("message").textContent = error.message;
    } finally {
      el("password").value = "";
      el("mfa").value = "";
      busy = false;
      updateControls();
    }
  });
  el("logoutButton").addEventListener("click", async () => {
    if (busy) return;
    busy = true;
    updateControls();
    try {
      await request("/auth/logout", {method: "POST"});
      el("message").textContent = "Logged out.";
    } catch (error) {
      el("message").textContent = `Local session cleared. ${error.message}`;
    } finally {
      clearSession();
      busy = false;
      updateControls();
    }
  });
  el("refreshButton").addEventListener("click", loadCatalog);
  el("ballotForm").addEventListener("submit", async event => {
    event.preventDefault();
    if (busy || submitted || !identity || !catalog || catalog.status !== "OPEN") return;
    const preferences = selections.map(item => ({candidate_id: item.candidateId, rank: Number(item.input.value)}));
    if (!el("confirmVote").checked || preferences.some(item => item.rank < 1) ||
        new Set(preferences.map(item => item.rank)).size !== preferences.length) {
      el("message").textContent = "Use every rank once and confirm your preferences.";
      return;
    }
    busy = true;
    updateControls();
    try {
      const receipt = await request("/ballots/submit", {method: "POST", body: JSON.stringify({election_id: catalog.election_id, preferences})});
      submitted = true;
      el("message").textContent = `Ballot accepted. Receipt: ${receipt.ballot_id}. Your vote has been recorded.`;
      selections.forEach(item => { item.input.value = ""; });
      el("confirmVote").checked = false;
    } catch (error) {
      el("message").textContent = `${error.message} If the connection was interrupted, check eligibility before retrying.`;
    } finally {
      busy = false;
      updateControls();
    }
  });
  loadCatalog();
})();
