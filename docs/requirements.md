# Security requirements register

The integrated prototype now contains implemented security controls. This register
replaces the old statement that every requirement was unimplemented.
It does not certify that the final assignment requirement set is complete.

## Existing requirement issues
The following 12 requirement issues were identified in the repository review.
Descriptions below summarise their scope. Priority and complexity reflect the
existing issue classifications and still need the owners' final review.

| ID | Requirement summary | Owner | Issue | Priority | Complexity |
| --- | --- | --- | --- | --- | --- |
| BAL-01 | Validate preferential rankings | Akshit | [#1](https://github.com/SHESHI7REDDY/Assignement-3_Group_51_Secure-software-systems/issues/1) | High | High |
| BAL-02 | Authorise ballot submission | Akshit | [#2](https://github.com/SHESHI7REDDY/Assignement-3_Group_51_Secure-software-systems/issues/2) | High | High |
| BAL-03 | Encrypt stored ballot data | Akshit | [#3](https://github.com/SHESHI7REDDY/Assignement-3_Group_51_Secure-software-systems/issues/3) | High | Medium |
| BAL-04 | Protect voter identity in ballot storage | Akshit | [#4](https://github.com/SHESHI7REDDY/Assignement-3_Group_51_Secure-software-systems/issues/4) | High | Low |
| ELIG-01 | Verify voter eligibility on the server | Ved | [#7](https://github.com/SHESHI7REDDY/Assignement-3_Group_51_Secure-software-systems/issues/7) | High | Medium |
| ELIG-02 | Prevent repeat voting atomically | Ved | [#8](https://github.com/SHESHI7REDDY/Assignement-3_Group_51_Secure-software-systems/issues/8) | High | High |
| ELIG-03 | Check authentication, roles, ownership and input | Ved | [#9](https://github.com/SHESHI7REDDY/Assignement-3_Group_51_Secure-software-systems/issues/9) | High | Medium |
| ELIG-04 | Separate voting authorisations and detect audit tampering | Ved | [#10](https://github.com/SHESHI7REDDY/Assignement-3_Group_51_Secure-software-systems/issues/10) | High | High |
| CAND-01 | Restrict candidate management to authorised staff | Shashi | [#12](https://github.com/SHESHI7REDDY/Assignement-3_Group_51_Secure-software-systems/issues/12) | High | High |
| CAND-02 | Protect candidates after voting starts | Shashi | [#13](https://github.com/SHESHI7REDDY/Assignement-3_Group_51_Secure-software-systems/issues/13) | High | Medium |
| CAND-03 | Validate and safely display candidate data | Shashi | [#14](https://github.com/SHESHI7REDDY/Assignement-3_Group_51_Secure-software-systems/issues/14) | High | Medium |
| CAND-04 | Use parameterised candidate database queries | Shashi | [#15](https://github.com/SHESHI7REDDY/Assignement-3_Group_51_Secure-software-systems/issues/15) | High | Low |

## Missing requirement definitions
The earlier plan reserved AUTH-01 to AUTH-04 for Varshil and RES-01 to RES-04
for Moinul. Matching requirement issues were not identified in the review.
Those eight reserved IDs are not yet eight confirmed unique requirements.
Their owners must reconcile the earlier assignments with the final implementation,
write the actual requirements and acceptance criteria, and create assigned issues.

The 12 listed issue classifications give five high-complexity, five medium-complexity
and two low-complexity requirements. The remaining approved requirements must bring
the final set to at least eight high and eight medium. Classify the actual scope
honestly; revise and justify scope or classifications with the group if needed.
Do not label a small change as complex only to reach the required totals.

## Acceptance review before submission
For every final requirement, add its alternatives and cost-benefit comparison,
selected solution, code paths, tests, evidence and report section. Use the assignment
status terms: fully implemented, partially implemented or not implemented.
The owner must check the full acceptance criteria before choosing that status.

Review these points in particular:
- CAND-01 issue #12 has outdated implementation text despite being closed.
- Real login uses server-verified sessions. Older mock or signed-token descriptions must match the final real-auth flow.
- Real ballot submission issues and consumes voting permission inside the integrated transaction. Do not describe the old direct authorisation route as the current voter flow.
- Ballot rows omit voter identity, but storage separation does not prove strong unlinkability against a database operator or timing analysis.
- A hash chain alone does not establish detection of deleted final events or a restored old database without an independent checkpoint.
- Backend MFA helpers do not provide a complete public enrolment interface.

See the [submission checklist](submission-checklist.md) for the remaining GitHub,
report and recording tasks. Record any unmet acceptance criterion as a limitation
or partial implementation rather than silently narrowing the original requirement.
