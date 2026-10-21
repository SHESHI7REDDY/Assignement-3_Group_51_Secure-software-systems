document.getElementById("ballotForm").addEventListener("submit", async function(event) {
    event.preventDefault();

    const candidateIds = [
        "CAND-001",
        "CAND-002",
        "CAND-003",
        "CAND-004"
    ];

    const preferences = [];

    for (const candidateId of candidateIds) {
        const value = document.getElementById(candidateId).value;

        if (!value) {
            document.getElementById("message").innerText =
                "Please rank every candidate.";
            return;
        }

        preferences.push({
            candidate_id: candidateId,
            rank: parseInt(value)
        });
    }

    const response = await fetch("/ballots", {
        method: "POST",

        headers: {
            "Content-Type": "application/json",
            "x-auth-token": "ballot-demo-token",
            "x-mock-role": "voter"
        },

        body: JSON.stringify({
            election_id: "ELECTION-2026",
            preferences: preferences
        })
    });

    const data = await response.json();

    const message = document.getElementById("message");

    if (response.ok) {
        message.innerText =
            "Ballot submitted successfully. Ballot ID: " + data.ballot_id;
    } else {
        message.innerText =
            "Ballot rejected: " + data.detail;
    }
});