# Awá

A single student's study planner. See `CONTEXT.md` for the domain glossary.

## Agent skills

### Issue tracker

Issues and specs live as GitHub issues, managed with the `gh` CLI. See `_docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles, each label string equal to its name. See `_docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` at the repo root, ADRs in `_docs/adr/`. See `_docs/agents/domain.md`.

## Message catalogs (i18n)

The UI is bilingual `es`/`en` (decision 18, ADR-0013). Source strings are
English; `LANGUAGE_CODE` is `es`. Catalogs live in `locale/<lang>/LC_MESSAGES/django.po`
— the `.po` is committed, the compiled `.mo` is git-ignored and rebuilt locally.

- Sync catalogs after adding `{% trans %}` / `gettext()` strings:
  `python manage.py makemessages -l es -l en --no-wrap`
- Compile before running or testing: `python manage.py compilemessages --ignore=.venv`
  (`studying/test_i18n.py` also compiles them in `setUpModule`).
- `makemessages`/`compilemessages` shell out to GNU `xgettext`/`msgfmt`. On this
  Windows machine they come from conda-forge `gettext-tools` 0.22.5 —
  `C:\Users\jeff0\anaconda3\Library\bin` must be on `PATH`. The old
  `defaults`-channel `gettext` 0.19.8.1 ships a **segfaulting `xgettext`** — do
  not use it.
- Domain data (Course names, códigos, university names) is never run through a
  catalog — it is substituted into the active locale's sentence as-is (ADR-0013).
