<!--
Sync Impact Report:
- Version change: 0.0.0 (Unratified Template) → 1.0.0
- List of modified principles:
  - [PRINCIPLE_1_NAME] → I. Self-Hosted Architecture & Data Sovereignty
  - [PRINCIPLE_2_NAME] → II. Modular Ingestion & Source Isolation
  - [PRINCIPLE_3_NAME] → III. Multimodal Ergonomics & Natural Language Robustness
  - [PRINCIPLE_4_NAME] → IV. Unified Volume Modeling & Peak Performance Analytics
  - [PRINCIPLE_5_NAME] → V. Philosophy-Steered, Adaptive AI Coaching
- Added sections:
  - Technical Architecture & Constraints (replaces [SECTION_2_NAME])
  - Development Workflow & Quality Standards (replaces [SECTION_3_NAME])
- Removed sections:
  - None
- Follow-up TODOs:
  - None
-->

# Coach3 Constitution

## Core Principles

### I. Self-Hosted Architecture & Data Sovereignty
All workout records, telemetry, biometrics, audio transcripts, and coaching philosophies MUST be stored on user-controlled, self-hosted infrastructure. The system MUST NOT transmit raw biometric, cardiovascular, or physical activity telemetry to unvetted third-party services. Any integration with external LLM APIs MUST require explicit opt-in, use privacy-preserving/anonymized payloads, or support fully local inference models. The user retains complete, irrevocable ownership and exportability of their entire training history.

### II. Modular Ingestion & Source Isolation
Third-party synchronization pipelines (e.g., Polar AccessLink for outdoor runs, Concept2 Logbook API for erg bike and rower sessions) and mobile multimodal inputs (e.g., gym voice logging) MUST operate as decoupled, independent ingestion adapters. Each adapter MUST map external data formats into canonical, strongly typed internal domain events. Ingestion pipelines MUST be idempotent, ensuring that repeated sync runs, network retries, or reprocessed voice entries never create duplicate workout sessions or distort historical volume metrics.

### III. Multimodal Ergonomics & Natural Language Robustness
Gym mode voice logging MUST prioritize minimal-friction input on mobile devices (e.g., iPhone) for strength and calisthenic workouts. Spoken descriptions (including compound exercises, bodyweight movements with added load, sets, reps, weight units, and RPE) MUST be parsed with high fault tolerance against background gym noise, colloquial terminology, and fatigue-induced phrasing. Parsed outputs MUST present a clear, human-verifiable intermediate representation for instant validation before persisting, with graceful fallback to clarification prompts when input is ambiguous.

### IV. Unified Volume Modeling & Peak Performance Analytics
The core analytics engine MUST normalize disparate training modalities into consistent, queryable volume and intensity aggregates:
- Endurance sessions: Zone 2 cardio duration, weekly mileage, heart rate distribution, pace, and power output.
- Strength and calisthenics sessions: Effective sets, total volume load (sets × reps × weight), estimated 1RM/5RM, and external load added to bodyweight.
Peak detection algorithms MUST be deterministic, historical, and transparently calculated to track personal records (PRs), recent peak performances, and progressive overload trends across arbitrary rolling windows.

### V. Philosophy-Steered, Adaptive AI Coaching
The AI coaching subsystem MUST decouple user-defined training philosophy from workout planning and retrospective feedback algorithms. Users MUST be able to define, inspect, and update their core training philosophies (e.g., polarized 80/20 endurance, progressive overload, conjugate system, rate of perceived exertion thresholds).
- **Planning Mode**: MUST generate forward-looking training schedules tailored to specific targets (e.g., VO2 max enhancement, absolute strength, endurance capacity) across defined timeframes.
- **Analysis Mode**: MUST evaluate recently completed workouts against active target priorities, assess adherence, calculate training stress, and prescribe concrete future adjustments.

## Technical Architecture & Constraints

- **Deployment Model**: The system MUST be deployable via self-hosted containers (e.g., Docker / Docker Compose) on personal hardware, homelabs, or private servers with minimal operational maintenance.
- **Persistence & Aggregation**: Relational or document persistence MUST enforce data integrity, provide robust migration paths, and support performant time-series aggregations for volume dashboards.
- **Client Experience**: The user interface MUST be mobile-optimized for iPhone operation (responsive web/PWA or companion client) with dependable audio recording and low-latency feedback.
- **Offline & Resiliency**: Mobile voice input and logging SHOULD buffer locally during transient network dropouts and synchronize seamlessly when the self-hosted backend becomes reachable.

## Development Workflow & Quality Standards

- **Spec-Driven Governance**: All new capabilities, schema changes, and integration connectors MUST follow the Spec Kit lifecycle, proceeding from specification (`/speckit-specify`) through architectural planning (`/speckit-plan`) and task breakdown (`/speckit-tasks`).
- **Comprehensive Verification**:
  - Deterministic unit tests MUST validate all volume calculations, unit conversions, and peak performance detection logic.
  - Contract/mock testing MUST be maintained for Polar and Concept2 API integrations.
  - Natural language parsing models MUST be continuously validated against a golden test suite of diverse spoken workout phrasing and edge cases (e.g., plate math, bodyweight modifiers, drop sets).
- **Non-Regression in Analytics**: Algorithms determining historical PRs, training volume, or zone allocations MUST pass regression test fixtures before deployment.

## Governance

This Constitution is the foundational governing document for the Coach3 project, superseding informal guidelines and ad-hoc conventions.
- **Amendments**: Core principles, architectural constraints, and governance standards may be amended only through explicit proposals documenting rationale, version updates, and migration strategies.
- **Versioning Policy**: Semantic versioning is enforced for this Constitution:
  - MAJOR version bumps indicate foundational principle removals or major governance shifts.
  - MINOR version bumps indicate added principles, new core sections, or substantial architectural expansions.
  - PATCH version bumps indicate wording refinements, clarifications, or formatting updates.
- **Compliance**: Every implementation plan, feature specification, and code review MUST verify adherence to the principles defined herein.

**Version**: 1.0.0 | **Ratified**: 2026-11-17 | **Last Amended**: 2026-11-17
