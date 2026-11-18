# Feature Specification: Adaptive AI Coaching Engine with Dual-Engine Architecture

**Feature Branch**: `feature/004-adaptive-ai-coaching`

**Created**: 2026-11-18

**Status**: Draft

**Input**: User description: "Feature 4, incorporating the dual-engine architecture: Google Gemini API (primary cloud LLM for high-reasoning critique and forward planning), Self-hosted llama.cpp server (local homelab inference via OpenAI-compatible /v1/chat/completions), Philosophy Steering (Polarized 80/20, progressive overload, RPE thresholds), Retrospective Workout Analysis & Forward Schedule Generation"

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Retrospective Workout Critique & Philosophy Adherence (Priority: P1) 🎯 MVP

An athlete completes a training session (or a full week of training) and requests coaching feedback. The AI coaching engine inspects the session data (duration, distance, Zone 1–5 distribution, strength volume load, RPE, and PR achievements) and evaluates it against the athlete's active philosophy (e.g. Polarized 80/20 or Progressive Overload). The system generates a structured coaching critique that highlights successes, flags deviations (e.g. "You spent 42% of your run in Zone 3 tempo gray zone rather than Zone 2 base"), and provides actionable recovery guidance.

**Why this priority**: Immediate feedback transforms raw workout tracking into deliberate, philosophy-driven athletic progression, closing the training feedback loop.

**Independent Test**: Can be independently tested by submitting a completed workout or multi-session summary with an active philosophy and verifying that the coaching engine returns a structured critique evaluating adherence, fatigue, and actionable adjustments.

**Acceptance Scenarios**:
1. **Given** an athlete with a Polarized 80/20 philosophy who logs a run with excessive Zone 3 heart rate time, **When** they request workout feedback, **Then** the coach explicitly identifies the intensity discipline failure and recommends pace adjustments for the next aerobic base session.
2. **Given** a resistance session with sets rated at RPE 9.5 or 10 on back squat, **When** analyzed against an RPE threshold rule ($\text{RPE} \le 8.5$), **Then** the coach identifies central nervous system strain and prescribes adequate rest before the next lower-body session.
3. **Given** a user viewing the analysis, **When** rendered, **Then** the critique presents distinct sections for Performance Summary, Philosophy Alignment, Fatigue/Strain Assessment, and Next Action Recommendations.

---

### User Story 2 - Forward-Looking Adaptive Training Schedule Generation (Priority: P1)

An athlete planning their upcoming training microcycle requests a forward schedule based on their current target (e.g., 10k race preparation, 315 lb squat peak, or general conditioning) and availability constraints (e.g. 4 training days per week, weekend long run). The AI coaching engine evaluates recent volume, fatigue trends, and personal records to generate a periodized forward training schedule with explicit daily workouts, target heart rate zones, exercise selections, sets, reps, and RPE boundaries.

**Why this priority**: Progressive overload and safe volume ramp rates require periodized forward planning rather than ad-hoc day-to-day guesswork.

**Independent Test**: Can be tested by requesting a 7-day schedule with defined targets and weekly frequency, verifying that the generated plan includes day-by-day workouts adhering to philosophy volume ceilings and rest day intervals.

**Acceptance Scenarios**:
1. **Given** an athlete targeting a 5k personal record with 4 available days, **When** generating a forward schedule, **Then** the system produces a periodized 7-day plan with one interval/tempo session, two Zone 2 base runs, one long run, and assigned rest days.
2. **Given** an athlete who experienced high volume load in the previous week, **When** generating the next week's schedule, **Then** the plan enforces a progressive overload ramp rate constraint ($\le 10\%$ volume increase) or prescribes a deload week if fatigue markers are elevated.
3. **Given** a generated forward plan, **When** accepted by the athlete, **Then** the planned workouts are saved as scheduled sessions accessible in the dashboard calendar.

---

### User Story 3 - Dual-Engine LLM Selection, Health Checks & Privacy Safeguards (Priority: P2)

A self-hosting athlete configures their preferred LLM inference engine. They can choose between the Google Gemini API (for advanced reasoning and long-horizon planning) or a self-hosted `llama.cpp` server running on their private homelab (for 100% offline, air-gapped local inference). The system validates connection health, reports latency, and guarantees that external cloud calls strip all Personally Identifiable Information (PII) and GPS route traces before transmission.

**Why this priority**: Fulfills Constitution Principle I (Data Sovereignty) by guaranteeing that athletes maintain full control over where their biometrics and training logs are processed.

**Independent Test**: Can be tested by toggling between Gemini and `llama.cpp` providers, running a provider health check, verifying structured response formatting across both engines, and inspecting outbound payloads to confirm zero PII leaks.

**Acceptance Scenarios**:
1. **Given** valid credentials for Google Gemini API, **When** selected as active provider, **Then** the system successfully executes coaching critique prompts and forward plan generations via Gemini.
2. **Given** a self-hosted `llama.cpp` server URL, **When** selected, **Then** the system sends requests via the OpenAI-compatible `/v1/chat/completions` endpoint and parses structured responses identically.
3. **Given** an athlete using the cloud provider (Gemini), **When** coaching payloads are constructed, **Then** user names, location names, and GPS coordinate arrays are completely omitted from the inference context.

---

### User Story 4 - Philosophy Configuration, Custom Rule Steering & Manual Context Ingestion (Priority: P2)

An athlete inspects, selects, or customizes their coaching philosophy rules. The system provides preset philosophies (Polarized 80/20 Endurance, Linear Progressive Overload, Conjugate/Hybrid Method) and allows athletes to adjust core steering parameters, such as target Zone 2 percentage, maximum weekly mileage progression cap, maximum allowable working RPE, and preferred weekly split. Furthermore, the athlete can manually load custom training context (e.g. pasting or uploading methodology notes, training book excerpts, personal injury constraints, or specific coach rules like "no barbell deadlifts due to lumbar strain; cap all tempo runs at 25 minutes"). The AI coaching engine ingests this manual context into its reasoning prompts, ensuring all critiques and generated forward plans strictly align with the athlete's personal training beliefs and physical constraints.

**Why this priority**: Fulfills Constitution Principle V by decoupling user-defined athletic philosophies from hardcoded coaching algorithms, ensuring advice matches the athlete's personal training belief system and real-world physiological context.

**Independent Test**: Can be tested by creating or modifying a coaching philosophy profile, altering parameter thresholds, adding custom context text (e.g. specific exercise exclusions or target paces), and verifying that subsequent AI critiques and forward schedules reflect the customized rules and manual context.

**Acceptance Scenarios**:
1. **Given** the preset philosophies, **When** an athlete switches from Polarized 80/20 to Progressive Overload, **Then** subsequent coaching reviews prioritize volume load progression over cardiovascular zone ratios.
2. **Given** custom parameter overrides (e.g. setting max RPE threshold to 8.0), **When** a workout with RPE 9.0 is evaluated, **Then** the AI critique flags the violation against the custom rule.
3. **Given** manually loaded training context (e.g. "Athlete recovering from lower back strain; avoid conventional deadlifts and substitute chest-supported rows; strictly limit weekly running mileage increase to 5%"), **When** forward training plans are generated or workouts are analyzed, **Then** the AI coach strictly adheres to the loaded context across all workout prescriptions and feedback.

---

## Edge Cases

- **Engine Unavailability or Timeout**: What happens if the local `llama.cpp` server is offline or the Gemini API returns a rate-limit/timeout?
  - System MUST fail gracefully with an informative user-facing diagnostic error, rather than crashing or freezing requests.
- **Provider Fallback Behavior**: Failover is strictly manual with clear diagnostic errors to prevent unintended external cloud API calls or data egress when the local server is temporarily offline; the user can manually switch active providers with one click.
- **Sparse or Zero Training History**: What happens when a new user requests forward schedule generation with zero logged workouts?
  - System MUST prompt for baseline fitness estimates (e.g. current 5k time, comfortable weekly mileage, or 1RM estimates) or generate a conservative introductory schedule without crashing.
- **Extreme Discrepancy Between Plan and Actuals**: What happens when an athlete logs 3x the prescribed volume or skips an entire week of workouts?
  - Analysis mode MUST recognize the massive deviation, avoid prescribing severe compensatory spikes, and recommend a re-baselining microcycle.
- **Conflicting Dual Goals**: What happens when an athlete sets competing goals (e.g. peak marathon endurance and 500 lb powerlifting deadlift simultaneously)?
  - Coach MUST flag concurrent interference effects and suggest phased block periodization rather than impossible simultaneous peaks.
- **Planning Horizon Boundaries**: Forward schedule generation in v1 supports rolling 1-to-2 week microcycles (7 or 14 days) dynamically adapted to recent volume, fatigue trends, and recovery markers.
- **Structured Schedule Storage Format**: Forward plans are stored in a hybrid architecture: retaining both the complete conversational Markdown plan narrative and discrete, structured `ScheduledWorkout` database entities for dashboard calendar integration.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support a dual-engine LLM provider architecture with configurable backends: Google Gemini API (cloud) and self-hosted `llama.cpp` server (local HTTP OpenAI-compatible endpoint).
- **FR-002**: System MUST allow the user to select the active LLM provider and configure endpoint credentials (API key for Gemini, base URL and model name for `llama.cpp`).
- **FR-003**: System MUST provide a provider health check capability that verifies connectivity, measures round-trip inference latency, and displays provider status.
- **FR-004**: System MUST scrub all PII (user names, emails, raw GPS route coordinates, location names) from prompt contexts before dispatching requests to external cloud LLM providers.
- **FR-005**: System MUST maintain configurable Coaching Philosophy profiles with adjustable parameters (e.g., target Zone 2 ratio, weekly volume ramp rate cap, maximum RPE limit, minimum rest days) AND support manual loading of custom context text/documents (e.g., personal training philosophies, methodology notes, injury history, movement exclusions) that are stored and injected into coaching prompts.
- **FR-006**: System MUST supply built-in preset philosophies: Polarized 80/20 Endurance, Progressive Overload Resistance, and Hybrid/Concurrent Training.
- **FR-007**: System MUST provide Retrospective Workout Analysis (Analysis Mode) evaluating completed sessions against active philosophy rules, volume metrics, and fatigue indicators.
- **FR-008**: System MUST generate structured coaching critiques containing: summary overview, philosophy adherence evaluation, strain/recovery assessment, and actionable next-session adjustments.
- **FR-009**: System MUST provide Forward Schedule Generation (Planning Mode) producing periodized workout schedules based on athlete goals, current volume baseline, and weekly frequency.
- **FR-010**: System MUST enforce philosophy safety boundaries in generated forward schedules (e.g., respecting maximum volume increase $\le 10\%$, preventing back-to-back heavy compound strength days).
- **FR-011**: System MUST expose REST API endpoints for coaching operations: `/api/v1/coaching/providers`, `/api/v1/coaching/philosophies`, `/api/v1/coaching/analyze`, and `/api/v1/coaching/plan`.
- **FR-012**: System MUST render a responsive visual Coaching UI supporting provider configuration, philosophy management, workout critique inspection, and forward plan viewing.

---

### Key Entities

- **LLMProviderConfig**: Configuration for active and standby inference engines (provider type: `gemini` | `llama_cpp`, endpoint URL, API key reference, model identifier, timeout, is_active).
- **CoachingPhilosophy**: Athlete's guiding methodology (name, description, target_zone2_pct, max_weekly_volume_ramp_pct, max_rpe_threshold, min_rest_days_per_week, primary_modality, custom_context_notes).
- **CoachingCritique**: Retrospective evaluation record (session_id or date window, philosophy_id, provider_used, adherence_score, summary_markdown, flags_and_warnings, actionable_recommendations, created_at).
- **TrainingSchedulePlan**: Forward-looking microcycle plan (target_goal, start_date, end_date, philosophy_id, planned_workouts_count, total_planned_distance, total_planned_volume, status: `active` | `completed` | `superseded`).
- **ScheduledWorkout**: Individual planned session within a schedule plan (target_date, discipline, planned_duration_min, target_distance_m, target_zones, strength_exercises, notes).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of outbound payloads to external cloud LLM providers are completely stripped of raw GPS coordinates and personal identifiers.
- **SC-002**: Retrospective workout analysis executes and renders structured critiques in under 4 seconds on Gemini and under 8 seconds on local homelab `llama.cpp` (hardware permitting).
- **SC-003**: 100% of generated forward training plans strictly adhere to configured philosophy boundaries (e.g. zero violations of the $10\%$ volume increase ceiling or user rest-day constraints).
- **SC-004**: Switching active providers between Gemini and `llama.cpp` requires zero server restarts and updates active inference immediately.
- **SC-005**: The coaching interface provides full offline functionality when configured with the local `llama.cpp` server, requiring zero external internet access.

---

## Assumptions

- **Local Server Compatibility**: The self-hosted `llama.cpp` server exposes the standard OpenAI-compatible API format (`POST /v1/chat/completions`) with JSON mode or grammar-constrained structured output support.
- **Gemini Credentials**: The user provides a valid Google Gemini API key via environment variable or self-hosted settings.
- **Single Active Athlete**: Coaching recommendations and schedules are contextualized for the primary self-hosted user's profile and training history.
- **Structured JSON Output**: Both LLM providers support structured JSON output or schema enforcement to ensure predictable parsing of critiques and schedule tables.
