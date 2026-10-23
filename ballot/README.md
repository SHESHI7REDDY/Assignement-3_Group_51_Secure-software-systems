# Historical standalone ballot demonstration

This folder contains an earlier isolated demonstration with mock authentication.
It is retained as development history. It is not the ballot module used by the
combined application and must not be presented as the final authentication flow.

Run the combined application through `app.main:app`. Its active ballot code is
in `app/ballot`, its page is under `frontend/ballot`, and its tests are under
`tests/ballot`. The root test configuration selects the shared `tests` directory.
Do not use the old mock token or role headers as integration evidence.
