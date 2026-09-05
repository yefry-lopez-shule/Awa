# Plans are authored as data files, not through the UI

Curriculum reference data — institutions, programs, plans, blocks, courses and
prerequisite edges — is authored as YAML under `plans/` and loaded by a management
command. There are no create or edit screens for any of it.

This is a deliberate exception to the "full custom UI, no Django admin" decision
(ADR-0005). That decision was about the daily loop, which is touched nightly.
Curriculum changes roughly once a year, and reference data that rarely changes
does not earn four CRUD screens on a v1 already carrying eight.

## Consequences

- Editing the curriculum requires a text editor and shell access. Acceptable: the
  user is the developer, and v1 runs locally.
- Plans are diffable, reviewable and shareable — a plan file for another UNED
  programme, or another university entirely, is a pull request rather than an
  afternoon of data entry.
- This is data, not hardcoding: nothing about a specific curriculum lives in
  Python.
