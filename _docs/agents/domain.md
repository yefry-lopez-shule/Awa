# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

This repo is **single-context** — one `CONTEXT.md` at the root, one ADR directory. Note the non-default path: ADRs live in **`_docs/adr/`**, not `docs/adr/`. Wherever a skill says `docs/adr/`, read `_docs/adr/`.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root — the Awá glossary (Curriculum, Studying, Planning, Reference).
- **`_docs/adr/`** — read ADRs that touch the area you're about to work in.
- **`_docs/scope.md`** — what the project is and isn't taking on.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) creates them lazily when terms or decisions actually get resolved.

## File structure

```
/
├── CONTEXT.md
├── AGENTS.md
└── _docs/
    ├── scope.md
    ├── agents/          ← this config
    └── adr/
        ├── 0001-status-is-a-code-enum.md
        ├── 0002-institution-agnostic-without-pluggable-rules.md
        ├── 0003-plans-are-data-files.md
        ├── 0004-difficulty-compounds.md
        ├── 0005-no-django-admin.md
        └── 0006-roadmap-is-reference-not-a-track.md
```

New ADRs go in `_docs/adr/`, numbered from the highest existing number.

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

`CONTEXT.md` carries explicit `_Avoid_` lists — those are binding, not advisory. Say **Enrollment**, not "registration"; **Course**, not "class" or "subject"; **Target**, not "goal" or "quota". Spanish terms in parentheses (*matrícula*, *cuatrimestre*) are there for recognition, not for use in code or issue titles.

If the concept you need isn't in the glossary yet, that's a signal — either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0004 (difficulty compounds) — but worth reopening because…_
