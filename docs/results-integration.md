# Results integration and final local test

The shared application now counts the accepted encrypted ballots from the ballot integration. It does not substitute the old ten-ballot `DEMO-001` fixture. Moinul's preferential counting and elimination code is reused.

## What changed

- `app.main` mounts `app.results.platform_router`, which requires a real authentication session with the `admin` role for counting, publication and audit access. The old `X-Results-Admin-Token` header does not grant access.
- Counting uses the configured `ELECTION_ID`, active candidates from the candidate database, and matching rows in `accepted_ballots` in the eligibility database.
- The election must be CLOSED before counting or publication. The local lifecycle command allows only DRAFT to OPEN and OPEN to CLOSED. CLOSED cannot be reopened.
- The server decrypts ballots in memory using the existing ballot key. It validates the stored preferences before passing them to the existing counting algorithm. It does not return or save plaintext ballots in the results database.
- A count snapshot, candidate metadata, source digest, result signature and results audit event commit in one transaction. Publication and its audit event also commit together. A failure rolls back the complete operation.
- The result signature uses HMAC-SHA256 with the configured results audit key. It covers the saved count, publication state and time, candidate metadata and source digest. Publication and public reads check integrity and verify that the closed-election source data has not changed since counting.
- Unpublished results return 404. Public results contain only aggregate counts, candidate names, the winner and publication information. There is no public endpoint for individual ballots or voter identities.
- The results page uses real administrator login. It keeps the session token in memory, clears passwords after login and uses textContent for displayed names and server messages.
- `data/platform_results.sqlite3` is the default integrated results database. The old fixture results database is not imported or reset. An explicit `RESULTS_DB_PATH` can override this default.
- Original fixture API tests remain isolated using `app.results.router`. This historical router is not mounted by the shared or standalone server entry points. The standalone results entry point now includes real authentication and the integrated results router.

## 1. Apply and test the patch

Work on `integration/full-platform`. Stop Uvicorn before changing server code, apply the supplied patch, then run:

```sh
source .venv-integration/bin/activate
python -m pytest -q
```

The added tests use temporary data. They do not delete, seed, submit or reset votes in your local demonstration databases.

## 2. Prepare persistent local configuration

From the project folder, with Uvicorn stopped:

```sh
python -m scripts.prepare_local_config
source .env.integration
python -m uvicorn app.main:app --reload --port 8000
```

The preparation command creates `.env.integration` only if it does not exist. It writes separate random eligibility and results audit secrets and keeps any explicitly configured data paths. The file has owner-only permissions and is ignored by Git. It never replaces an existing configuration. If a results audit already exists, an absent original results key causes an error instead of creating a replacement key.

Always run `source .env.integration` in the terminal that starts the server. The application does not automatically load that file. Keep it private and backed up with `data/ballot_key.key`. Do not put secret files, tokens, passwords or databases in your report or commits.

Previous eligibility audit records are preserved. If development used random per-process pseudonym keys, older actor pseudonyms may differ from future ones; preparing persistent configuration does not rewrite those old records.

## 3. Prepare a separate results administrator

Keep `voter_1` as a voter and `officer_1` as an officer.

In `/docs`, register a separate account, such as `results_admin`, using POST `/auth/register` and a private password of at least 12 characters containing letters and numbers. Its initial role is voter. Public registration cannot grant administrator privileges.

In a second project terminal:

```sh
source .venv-integration/bin/activate
python -m app.auth.demo_admin results_admin
```

This trusted local command requires access to server database files. It refuses a linked voter or an officer account, preserves the account password and revokes any earlier sessions when changing the role. Log in again afterward. Repeating setup for the same administrator does not replace credentials or reset voting records.

## 4. Check that counting is blocked while OPEN

Open `http://127.0.0.1:8000/static/results/index.html` and log in as the results administrator. The page loads the configured election ID. If the election is still OPEN, click Count accepted ballots. Expected: rejection explaining that the election must be closed. A published-result lookup should return 404 before publication.

## 5. Close, count and publish

Close the election only when all intended voting tests are finished. Closing prevents further votes and cannot be reversed through the lifecycle command.

```sh
python -m app.ballot.lifecycle DEMO-A3-ELECTIONS CLOSED
```

Reload the results page and log in again if needed. Click Count accepted ballots once. The accepted-ballot total should match the number of successful integrated submissions. If exactly one ballot ranked Varshil first, the expected total is 1 and the winner is DEMO-C001 (Varshil). Additional successful ballots can change the result.

Before publication, confirm that public lookup still returns 404. Then click Publish result. Public lookup should now show the result without requiring login. Click Verify audit integrity and Load audit events as the administrator. Expected audit event sequence: COUNT_COMPLETED, RESULT_PUBLISHED.

Repeating count or publication returns a conflict and does not overwrite the saved result. A tied elimination returns an unresolved-tie error; the prototype does not invent a winner. Do not reset voting flags, delete results or reopen the election to manufacture a different result.

## Report and presentation evidence

Capture these screens, with credentials hidden:

- The complete test-suite result on the integration branch.
- A successful ballot receipt and the same voter's ALREADY_VOTED eligibility decision.
- Counting rejected while the election is OPEN.
- The accepted-ballot count after closure.
- Public lookup rejected before publication, then successful after publication.
- Results audit verification and the count/publication events.
- An ordinary voter or officer rejected from a results administrator operation.

Describe the actual local result and test evidence. Fixture tests are algorithm examples; they are not evidence that ten people voted in your integrated demonstration.

## Limits and remaining submission work

This is a local coursework prototype. Local operator commands assume trusted filesystem access. HMAC verification depends on keeping the key separate from database copies; a trusted external checkpoint would be needed to detect complete rollback or tail truncation. There is no implemented operational tie procedure or independent election certification. The encryption and separate table columns do not establish cryptographic voter anonymity against a database operator.

The results audit is separate from the eligibility audit. These are not one cross-module audit chain. The source digest protects the counted snapshot after counting; it does not provide end-to-end voter verifiability or a signed record of the entire election history before counting. Ballots and source data should be preserved after closure.

Finish the actual browser checks before merging the integration branch into main. Review all requirement issues, report implementation statuses, architecture, costs and benefits, test evidence, contribution history and the group recording. Passing the suite alone does not prove every selected assignment requirement is fully implemented.
