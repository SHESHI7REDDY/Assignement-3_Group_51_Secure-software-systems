"use strict";

(() => {
  const manageForm = document.getElementById("manage-form");
  const message = document.getElementById("manage-status");
  const tokenField = document.getElementById("manage-token");
  const value = (id) => document.getElementById(id).value.trim();

  manageForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (loading) return;
    const action = event.submitter?.value;
    if (!["create", "edit", "deactivate"].includes(action)) return;
    const electionId = electionInput.value.trim();
    const candidateId = value("manage-id");
    const token = tokenField.value.trim();
    const name = value("manage-name");
    const party = value("manage-party");
    const order = Number(value("manage-order"));

    if (!/^[A-Za-z0-9_-]{1,64}$/.test(electionId) || !token) {
      message.textContent = "Enter a valid election ID and officer token.";
      return;
    }
    if (action !== "create" && !candidateId) {
      message.textContent = "Copy the candidate ID from the list above.";
      return;
    }
    if (action !== "deactivate" && (!name || !party ||
        !Number.isInteger(order) || order < 1 || order > 1000)) {
      message.textContent = "Enter a name, party and ballot position from 1 to 1000.";
      return;
    }
    if (action === "deactivate" &&
        !window.confirm(`Deactivate candidate ${candidateId} in ${electionId}?`)) return;

    const query = new URLSearchParams({ election_id: electionId });
    let url = "/candidates";
    if (action !== "create") {
      url += `/${encodeURIComponent(candidateId)}`;
      if (action === "deactivate") url += "/deactivate";
      url += `?${query}`;
    }
    const headers = { Accept: "application/json", Authorization: `Bearer ${token}` };
    const options = { method: action === "edit" ? "PATCH" : "POST", headers };
    if (action !== "deactivate") {
      headers["Content-Type"] = "application/json";
      const payload = { name, party, ballot_order: order };
      if (action === "create") payload.election_id = electionId;
      options.body = JSON.stringify(payload);
    }

    loading = true;
    loadButton.disabled = true;
    electionInput.readOnly = true;
    const controls = manageForm.querySelectorAll("input, button");
    controls.forEach((control) => { control.disabled = true; });
    message.textContent = "Saving…";
    let saved = false;
    try {
      const response = await fetch(url, options);
      if (!response.ok) {
        const errors = {
          401: "Invalid or expired token.",
          403: "You cannot manage this election.",
          404: "Election or candidate not found.",
          409: "Election is locked or the ballot position conflicts.",
          422: "Candidate information failed validation.",
          503: "Authentication verification is unavailable or not configured.",
        };
        throw new Error(errors[response.status] || `Request failed: HTTP ${response.status}.`);
      }
      saved = true;
      clearResults("Refreshing candidates…");
      const refresh = await fetch(`/candidates?${query}`, {
        headers: { Accept: "application/json" },
      });
      if (!refresh.ok) throw new Error("Refresh failed.");
      const data = await refresh.json();
      if (!Array.isArray(data.candidates) || data.election_id !== electionId) {
        throw new Error("Unexpected list response.");
      }
      renderCandidates(data.candidates, electionId);
      setStatus(`Loaded ${data.candidates.length} active candidates.`, "success");
      message.textContent = "Change saved and candidate list updated.";
    } catch (error) {
      message.textContent = saved
        ? "Change saved. Reload the candidate list before making another change."
        : (error instanceof Error ? error.message : "Request failed.");
    } finally {
      tokenField.value = "";
      controls.forEach((control) => { control.disabled = false; });
      loading = false;
      loadButton.disabled = false;
      electionInput.readOnly = false;
    }
  });
})();
