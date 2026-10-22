# Security Policy

IntegrityWatch is a security tool, so reports about its own weaknesses are taken seriously.

## Reporting a vulnerability
Please **do not** open a public issue for a security problem. Use GitHub's private
reporting instead: open the **Security** tab of this repository and choose
**Report a vulnerability**.

Include what you found, how to reproduce it, and the impact you expect.
I'll respond as soon as I can.

## Known limitations
These are documented design limits, not vulnerabilities (see the README):
- If an attacker can modify the baseline file, they can hide changes.
- `watch` polls on an interval and can miss a change that is made and reverted between checks.
