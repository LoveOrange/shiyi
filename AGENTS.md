# Shiyi Agent Guide

Shiyi is still in MVP. Optimize for simple, direct progress over long-lived compatibility layers.

## Design Principles

- Lightweight: add the smallest code and spec surface that proves the current product need.
- Simple: prefer one clear model/function/path over adapter layers, aliases, or migration shims.
- Elegant: keep names aligned with the domain language used in specs and tests.
- Declarative: make behavior explicit in typed contracts, tests, and specs instead of hidden conventions.
- Idempotent: repeated pipeline runs should be safe and should not duplicate durable records/artifacts.

## MVP Compatibility Policy

Do not add backward-compatibility aliases, compatibility names, migration branches, or compatibility-style fixes unless Lin explicitly asks for them.

When a boundary name changes during MVP, rename it directly across code, tests, and docs. Broken old imports are acceptable because there are no supported external consumers yet.

## Overdesign Guardrail

Before adding an abstraction, ask:

1. Is it required by the current MVP acceptance criteria?
2. Can the same product behavior be expressed with fewer moving parts?
3. Does it improve idempotency, clarity, or source-boundary isolation now?

If not, do not add it.
