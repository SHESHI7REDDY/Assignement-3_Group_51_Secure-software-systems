"use strict";

const form = document.getElementById("election-form");
const electionInput = document.getElementById("election-id");
const loadButton = document.getElementById("load-button");
const statusMessage = document.getElementById("status");
const rows = document.getElementById("candidate-rows");
const table = document.getElementById("candidate-table");
const caption = document.getElementById("table-caption");
const count = document.getElementById("candidate-count");
const emptyState = document.getElementById("empty-state");

let loading = false;


function setStatus(message, state) {
  statusMessage.textContent = message;
  statusMessage.dataset.state = state;
}


function clearResults(message) {
  rows.replaceChildren();
  table.hidden = true;
  count.textContent = "0 candidates";

  emptyState.hidden = false;
  emptyState.textContent = message;
}


function renderCandidates(candidates, electionId) {
  rows.replaceChildren();

  for (const candidate of candidates) {
    const row = document.createElement("tr");

    const values = [
      candidate.ballot_order,
      candidate.name,
      candidate.party,
      candidate.candidate_id,
    ];

    for (const value of values) {
      const cell = document.createElement("td");

      // Display received values as text, not HTML.
      cell.textContent = String(value ?? "");

      row.appendChild(cell);
    }

    rows.appendChild(row);
  }

  caption.textContent =
    `Candidates for ${electionId} in ballot order`;

  count.textContent =
    `${candidates.length} candidate${candidates.length === 1 ? "" : "s"}`;

  table.hidden = candidates.length === 0;
  emptyState.hidden = candidates.length !== 0;
  emptyState.textContent =
    "This election has no active candidates.";
}


form.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (loading) {
    return;
  }

  const electionId = electionInput.value.trim();

  if (!/^[A-Za-z0-9_-]{1,64}$/.test(electionId)) {
    clearResults("No results to display.");

    setStatus(
      "Use 1–64 letters, numbers, underscores or hyphens for the election ID.",
      "error"
    );

    return;
  }

  loading = true;
  loadButton.disabled = true;
  electionInput.readOnly = true;

  clearResults("Loading candidates…");
  setStatus("Loading candidates…", "loading");

  try {
    const query = new URLSearchParams({
      election_id: electionId,
    });

    const response = await fetch(`/candidates?${query}`, {
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      const message = response.status === 404
        ? "Election not found. Check the election ID."
        : `Unable to load candidates (HTTP ${response.status}).`;

      throw new Error(message);
    }

    const data = await response.json();

    if (
      !Array.isArray(data.candidates)
      || data.election_id !== electionId
    ) {
      throw new Error(
        "The server returned an unexpected response."
      );
    }

    renderCandidates(data.candidates, electionId);

    setStatus(
      `Loaded ${data.candidates.length} active candidates.`,
      "success"
    );

  } catch (error) {
    clearResults("No results to display.");

    setStatus(
      error instanceof Error
        ? error.message
        : "Unable to load candidates.",
      "error"
    );

  } finally {
    loading = false;
    loadButton.disabled = false;
    electionInput.readOnly = false;
  }
});