# Security policy

## Supported versions

deli is early and moves quickly, so only the latest release gets fixes. If you are on an
older version, `pip install -U deli-slicer` before reporting.

## What counts

deli talks to printers on your network (`deli send`), fetches profiles from OrcaSlicer's
GitHub and models from Printables, and serves `deli view` on a local port. Things worth
reporting privately include:

- a way for a crafted `deli.toml`, model file or profile to run code or write outside
  the project folder
- `deli view` being reachable, or able to change files, from somewhere it should not be
- credentials or printer addresses ending up somewhere they should not, such as logs or
  G-code
- anything in the wheels' bundled libraries ([THIRD-PARTY-NOTICES.md](../THIRD-PARTY-NOTICES.md))
  that affects deli in practice

A printer's own firmware or network service is out of scope; report that to its maker.

## Reporting a vulnerability

Please do not open a public issue. Use
[Report a vulnerability](https://github.com/dcruver/deli-slicer/security/advisories/new)
on the Security tab, or email donald@cruver.ai with "deli security" in the subject.

Say which version (`deli --version`), your platform, and how to reproduce it. You should
hear back within a week. Once a fix is released, the advisory will credit you unless you
would rather it did not.
