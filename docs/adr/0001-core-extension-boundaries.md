# ADR 0001: Core Extension Boundaries

- Status: Draft
- Date: 2026-05-12

## Context

Shiyi needs to support many information sources, optional AI providers for neutral annotations, and storage backends. If core directly depends on any one implementation, the project will become hard to extend and hard to trust.

## Decision

Shiyi core will define three primary extension boundaries:

1. Adapter
2. Normalizer
3. AI Provider
4. Artifact Store and Event Record Store

Core owns orchestration, validation, policy, idempotency, observability, and contract definitions. Implementations live outside the core boundary and communicate through typed ports. Product-specific insight, ranking, scoring, and editorial decisions stay outside Shiyi.

## Consequences

Positive:

- Users can replace integrations independently.
- Public contracts can be tested and versioned.
- Core remains small and auditable.

Trade-offs:

- The initial API design requires more discipline.
- Contract testing becomes mandatory for ecosystem quality.
- Some convenience features must wait until the boundaries stabilize.
