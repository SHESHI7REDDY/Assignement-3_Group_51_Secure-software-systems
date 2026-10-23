# One-click local demonstration

This launcher is for a local assessment demonstration. It uses the real combined
application and real authentication. It does not turn on mock authentication.

## First launch
1. Install Python 3.12 or newer from https://www.python.org/downloads/ if it is not already installed. The launcher does not install Python or require Homebrew.
2. Clone this repository, or download its ZIP from GitHub and extract it.
3. On macOS, double-click `Start-Demo.command`. On Windows, double-click `Start-Demo.bat`.
4. Keep the terminal window open. The first launch installs dependencies and needs internet access; it can take a few minutes.
5. The browser opens at http://127.0.0.1:8000 and a private text file opens with the prepared account usernames and passwords. No account registration or manual database edits are needed for the demo.

If a downloaded macOS file is blocked, use Finder's **Open** option and follow the
macOS prompt if offered. Do not disable system security. If the file lacks execute
permission after ZIP extraction, open Terminal in the project folder and run:

```sh
bash Start-Demo.command
```

On Linux, or as an alternative on macOS:

```sh
python3.12 scripts/launch_demo.py
```

Python must support `venv` and `pip`. Use a supported desktop computer with a web
browser. Windows launch has not been verified on a Windows machine.

## Demonstration order
Use `DEMO-A3-ELECTIONS` throughout.

| Stage | Account and action |
| --- | --- |
| DRAFT | Use `demo_officer` to manage candidates. Create, edit and deactivate an extra candidate. Keep the original four active for a simple ballot demonstration. |
| OPEN | In the launcher terminal, enter **2**. Use `demo_voter` (V0001) for an eligibility check and one ballot. A second ballot should be rejected. |
| Negative check | Use `demo_ineligible` (V0002), an underage fictional voter, to demonstrate failed eligibility. A voter must also be denied candidate management. |
| CLOSED | In the launcher terminal, enter **3**. Use `demo_admin` to count and publish results. Then view the published result without logging in. |
| Stop | In the launcher terminal, enter **5**, or press Ctrl+C. |

The account details are in `.demo-data/DEMO-ACCOUNTS.txt`. The passwords are
randomly generated on first launch. They persist across launches, so use the file
from your own computer rather than another member's credentials. If the candidate
page asks for a bearer token, log in through the authentication page or
`POST /auth/login` in `/docs`, then paste only the returned `access_token` value.
This is a real session token. Never record it or include it in submitted screenshots.

Opening and closing elections remains a trusted local operator action in the
terminal. The launcher does not add a public API for granting roles or changing
state. User requests still pass the existing authentication and permission checks.

## Data and repeat launches
- The launcher creates `.venv-demo` for dependencies and `.demo-data` for fictional accounts, databases, encryption keys and settings. Git ignores both folders.
- Your existing `data/` databases, `.env.integration` settings, accounts and completed elections are not modified by the launcher.
- Repeat launches preserve candidate edits, votes, election state and results. They do not reopen a CLOSED election or make a voter eligible to vote twice.
- For another full demonstration, use a separate fresh checkout in a different folder. Keep the old demo data and keys if you need its evidence.
- The server binds only to `127.0.0.1`. It is not deployed for access from other computers.
- If port 8000 is already occupied, the launcher stops and explains the problem. Stop the previous server and try again; it does not kill other processes.
- If startup fails, inspect `.demo-data/server.log`. Keep private files and keys out of GitHub, reports and recordings.

A successful launch does not make this classroom prototype suitable for a public
election. The limitations described in the project README still apply.
