
# Authentication and User Security Subsystem

## Project
Electronic Voting Platform – Secure Software Systems
Group 51

Subsystem owner: Varshil Nehal Shah

## 1. Subsystem Overview

This module provides a standalone authentication
prototype using FastAPI, Python and SQLite.

The subsystem supports user registration, credential
verification, multifactor authentication utilities,
secure sessions, account lockout, role-based access
control and authentication audit events.

It is an educational prototype, not a production
Australian election system.

## 2. Implemented Security Controls

| Control | Implementation |
|---|---|
| Input validation | Pydantic request models |
| Password storage | Argon2id password hashing |
| Database access | Parameterised SQLite queries |
| Registration | Duplicate username rejection |
| Login | Credential verification |
| MFA | TOTP-based authentication |
| MFA secret protection | Fernet authenticated encryption |
| Session management | Random opaque bearer tokens |
| Session storage | SHA-256 token hashes |
| Session expiration | 30-minute lifetime |
| Logout | Session revocation |
| Failed-login protection | Five-attempt temporary lockout |
| Access control | Voter and admin roles |
| Audit logging | SQLite security event records |

## 3. Main Implementation Files

app/auth/schemas.py
- Registration, login and response validation.

app/auth/repository.py
- SQLite user, MFA and session persistence.
- Failed-login state and lockout tracking.

app/auth/service.py
- Authentication business rules.
- Password verification.
- MFA enrolment logic.
- MFA-enforced session creation.

app/auth/router.py
- Authentication REST endpoints.
- Session verification and logout.
- Administrator-only audit endpoint.

app/auth/mfa.py
- TOTP secret generation and code verification.

app/auth/mfa_security.py
- MFA secret encryption and decryption.

app/auth/sessions.py
- Session token generation, validation and revocation.

app/auth/audit.py
- Authentication security event recording.

app/auth/standalone.py
- Standalone FastAPI application.

frontend/auth.html
- Registration, login, verification and logout UI.

## 4. Authentication API Endpoints

POST /auth/register
- Registers a new prototype user account.

POST /auth/login
- Checks credentials and enforces MFA when enabled.
- Returns a session token after successful authentication.

GET /auth/verify
- Requires an active bearer session.
- Returns public account information.

POST /auth/logout
- Requires an active bearer session.
- Revokes the current session.

GET /auth/admin/audit
- Requires an authenticated administrator role.
- Returns recent authentication audit events.

## 5. Automated Testing

The authentication test files cover:

- Registration and login input validation.
- Argon2id password verification.
- MFA secret generation and TOTP verification.
- Encrypted MFA enrolment and activation.
- Session creation, expiry and revocation.
- MFA login enforcement and code replay rejection.
- Authentication API behaviour.
- Account lockout and recovery.
- Role-based access control.
- Security audit events.
- Frontend availability and API integration.

Last recorded authentication test result:

60 passed, 1 dependency deprecation warning.

This result must be rechecked against the final code.

## 6. Running the Standalone Module

From the project root, activate the Python
virtual environment and install dependencies.

Run:

python -m pip install -r requirements.txt

Start the standalone FastAPI application:

python -m uvicorn app.auth.standalone:app --reload

API documentation:

http://127.0.0.1:8000/docs

Authentication frontend:

http://127.0.0.1:8000/static/auth.html

Run authentication tests:

python -m pytest -q tests/test_varshil_*.py

## 7. Integration Requirements

Other subsystems should use authenticated session
verification rather than trusting a username or
role supplied directly by a frontend request.

Administrative actions must validate the user's
role on the server.

The voter eligibility subsystem must separately
establish voter eligibility.

The ballot subsystem must preserve ballot secrecy.
Authentication records and session identifiers
must not be stored alongside individual vote choices.

The final team application must explicitly integrate
the authentication router and associated security
dependencies.

## 8. Known Limitations

- Public MFA enrolment APIs and a complete enrolment
  UI are not yet implemented.
- SQLite audit records are not tamper-resistant.
- Distributed brute-force protection is not implemented.
- Account lockout may be abused to deny access to users.
- Concurrent login and lockout races require hardening.
- Session storage and management require further
  review before production deployment.
- Browser security requires HTTPS, secure deployment
  settings and further security testing.
- Encryption key management requires secure deployment
  configuration and backup procedures.
- Voter identity and eligibility are not established
  by authentication alone.
- Security testing is limited to the prototype's
  implemented behaviour.

## 9. Security and Deployment Notes

Do not commit:

- Real user credentials.
- SQLite databases containing sensitive user data.
- MFA encryption keys.
- Session bearer tokens.
- Local environment secrets.

The prototype should not be exposed as a public
internet-facing election system without further
security engineering, review and assessment.

## 10. Development and Version Control

Development branch:

feature/varshil-auth

Each implementation milestone is tracked through
meaningful source code changes and Git commits.

Final integration should occur through a reviewed
pull request into the team's main branch.
