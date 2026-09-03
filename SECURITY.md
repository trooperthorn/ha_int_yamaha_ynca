# Security Policy

## Reporting a vulnerability

Do not open a public issue containing exploit details, credentials, private
addresses, or logs. Use GitHub's private vulnerability-reporting feature for
this repository. If private reporting is unavailable, open a minimal issue
asking the maintainer to establish a private channel; omit technical details.

Include the affected version/commit, prerequisites, impact, a minimal
reproduction, and suggested remediation. Remove tokens, API keys, cookies,
and private network details (host, port, serial device path).

## Response targets

These are project targets, not an SLA: acknowledge critical/high reports in
three business days, establish severity and containment in seven, and publish
a coordinated fix/advisory as soon as safely validated. Lower-severity issues
are prioritized by exploitability and impact.

## Supported version

Only the latest published release and the default branch receive security
fixes. Operators should keep the integration and Home Assistant Core updated
and retain a tested rollback/backup.

## Security boundaries

Yamaha (YNCA) is a privileged Home Assistant integration, not a sandbox. It
connects to a receiver over a serial link or a local network socket using
credentials and connection details the operator supplies through the config
flow; it does not authenticate the receiver or encrypt the YNCA protocol
itself, both of which are constraints of the underlying hardware and
protocol, not of this integration. It cannot prevent a malicious integration
in the same Python process from reading shared memory or files.
