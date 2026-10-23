"""Check real login and eligibility over HTTP without displaying credentials.

Run from the project root: python scripts/check_identity_link.py
The shared server must already be running on 127.0.0.1:8000.
This check never requests voting authorisation and never submits a ballot.
"""

import getpass
import sys

import httpx


def main():
    username = input("Demo username [voter_1]: ").strip() or "voter_1"
    password = getpass.getpass("Demo account password (hidden): ")
    token = None
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=10, trust_env=False) as client:
        try:
            response = client.post("/auth/login", json={
                "username": username, "password": password, "mfa_code": None,
            })
            password = ""
            print("Login HTTP", response.status_code)
            response.raise_for_status()
            token = response.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            response = client.get("/auth/verify", headers=headers)
            print("Verify HTTP", response.status_code)
            response.raise_for_status()
            identity = response.json()
            print("Verified identity:", {
                key: identity.get(key) for key in
                ("user_id", "username", "role", "voter_id", "managed_election_ids")
            })
            if not identity.get("voter_id"):
                print("No electoral-roll link is configured for this account.")
                return 1
            response = client.post("/eligibility/check", headers=headers,
                                   json={"voter_id": identity["voter_id"]})
            print("Eligibility HTTP", response.status_code)
            response.raise_for_status()
            decision = response.json()
            print("Eligibility decision:", decision)
            if decision.get("election_id") != "DEMO-A3-ELECTIONS":
                print("Election mismatch: restart the server with the agreed ELECTION_ID.")
                return 1
            if not decision.get("eligible"):
                print("Account authenticated, but eligibility was not granted.")
                return 1
            print("PASS: real login, identity link and eligibility check work together.")
            print("No voting authorisation was issued and no ballot was submitted.")
            return 0
        except (httpx.HTTPError, KeyError, ValueError) as error:
            print("Check failed:", str(error))
            print("Check the server logs and verifier configuration. Do not share tokens.")
            return 1
        finally:
            if token:
                try:
                    response = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
                    print("Test session logout HTTP", response.status_code)
                except httpx.HTTPError:
                    print("Test session logout unavailable; it will expire normally.")


if __name__ == "__main__":
    sys.exit(main())
