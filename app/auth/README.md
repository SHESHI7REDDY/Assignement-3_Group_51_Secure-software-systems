# Authentication module

Owner: Varshil.

The combined application uses this module for account registration, login,
server-side sessions, identity verification, logout and administrator audit access.
Passwords use Argon2id. Public registration creates voters only.

Read the [authentication implementation notes](../../docs/varshil_auth_implementation.md)
for the detailed design and tests. Run the full suite with `python -m pytest -q`.
Use the authentication page linked from the combined application's home page.

Trusted local profile links connect an account to a fictional electoral-roll ID.
Officer roles and election assignments must be provisioned by a trusted operator.
An account link does not by itself grant eligibility or officer permissions.

MFA helpers and login enforcement exist in the backend. A complete public MFA
enrolment API and interface are not provided; report this limitation explicitly.
