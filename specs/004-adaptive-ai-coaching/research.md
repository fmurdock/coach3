# Phase 0 Research: Adaptive AI Coaching Engine with Dual-Engine Architecture

**Feature**: `004-adaptive-ai-coaching`  
**Date**: 2026-11-18  
**Branch**: `feature/004-adaptive-ai-coaching`  
**Status**: Completed  

---

## 1. Technical Objectives & Constraints

This feature delivers the AI coaching engine for Coach3, realizing **Constitution Principle V**:
> *"The AI coaching subsystem MUST decouple user-defined training philosophy from workout planning and retrospective feedback algorithms. Users MUST be able to define, inspect, and update their core training philosophies (e.g. polarized 80/20 endurance, progressive overload, conjugate system, rate of perceived exertion thresholds). Planning Mode MUST generate forward-looking training schedules tailored to specific targets. Analysis Mode MUST evaluate recently completed workouts against active target priorities, assess adherence, calculate training stress, and prescribe concrete future adjustments."*

And strictly adhering to **Constitution Principle I**:
> *"Any integration with external LLM APIs MUST require explicit opt-in, use privacy-preserving/anonymized payloads, or support fully local inference models."*

---

## 2. Key Architectural Decisions & Analysis

### 2.1 Dual-Engine LLM Integration Strategy: Unified Async HTTP Client vs SDKs
- **Decision**: Implement an abstract `BaseLLMClient` with two specialized async HTTP adapters (`GeminiClient` and `LlamaCppClient`) powered by `httpx`.
- **Rationale**:
  - `httpx` is already an established, battle-tested dependency in Coach3 (used across Polar, Concept2, and FastAPI integration tests).
  - Both Google Gemini (via `https://generativelanguage.googleapis.com/v1beta/models/...:generateContent`) and `llama.cpp` (via `POST /v1/chat/completions`) provide clean, well-documented REST APIs with JSON schema and structured output support.
  - Using `httpx` avoids bloated SDK dependencies, prevents dependency conflicts across Python versions, and enables clean, deterministic offline mock testing in `pytest` with `respx` or mock transports.
- **Alternatives Considered**:
  - `google-genai` SDK + `openai` SDK: Adds multiple external client libraries with divergent connection pool configurations, retry policies, and extra dependency overhead.

### 2.2 Structured JSON Output & Schema Enforcement
- **Decision**: Require structured JSON output using native provider capabilities:
  - **Gemini**: `generationConfig: { responseMimeType: "application/json", responseSchema: ... }`
  - **`llama.cpp`**: `response_format: { type: "json_object" }` combined with system prompt JSON schema guidance.
  - **Application Layer**: Parse responses through Pydantic v2 schemas (`CoachingCritiqueResponse`, `SchedulePlanResponse`) with validation error fallbacks.
- **Rationale**: Guarantees deterministic parsing into relational database models (`CoachingCritique`, `ScheduledWorkout`) while allowing the LLM to output rich Markdown commentary inside designated fields.

### 2.3 Philosophy Steering & Manual Context Ingestion Architecture
- **Decision**: Structure training philosophies with a two-tier model:
  1. **Deterministic Steering Parameters**: Numeric thresholds (`target_zone2_pct`, `max_weekly_volume_ramp_pct`, `max_rpe_threshold`, `min_rest_days_per_week`).
  2. **Unstructured Manual Context Notes**: Free-form text (`custom_context_notes`) where the user can paste methodology notes (e.g. Jack Daniels VDOT, Stephen Seiler 80/20 guidelines), injury history (e.g. "lumbar spine recovery, avoid conventional deadlifts"), or coach rules.
- **Rationale**: Gives athletes full creative freedom to instruct the AI with their own training philosophy and medical/physical context while maintaining programmatic guards on volume ramp rates.

### 2.4 Privacy Scrubbing & Data Sovereignty (Constitution I)
- **Decision**: Outbound payload pipeline passes through a strict `PrivacyScrubber` before hitting external cloud APIs:
  - Strips athlete names, emails, user IDs, and account credentials.
  - Strips GPS route coordinate arrays (`GPSRoutePoint`) and location titles.
  - Transmits strictly mathematical training aggregates: workout discipline, duration in seconds, heart rate zone durations, strength exercise canonical names, sets, reps, weight, RPE, and user-provided custom context notes.
- **Rationale**: 100% compliant with Constitution Principle I. Cloud providers receive only anonymous athletic metrics.

### 2.5 Provider Failover Policy
- **Decision**: Strictly manual failover with diagnostic status indicators.
- **Rationale**: Prevents accidental cloud billing or unwanted third-party data egress if the athlete's local homelab `llama.cpp` server is temporarily powered down. If an active provider fails or times out, the system returns a clear error and allows the user to switch with a single click.

---

## 3. Constitution Compliance Check

| Principle | Requirement | Design Status | Compliance Assessment |
|---|---|---|---|
| **I. Self-Hosted Architecture & Sovereignty** | Local data storage; opt-in cloud LLM; privacy scrubbing; local model support. | **PASS** | Dual-engine design supports 100% local `llama.cpp`; Gemini calls scrubbed of PII and GPS traces. |
| **II. Modular Ingestion & Source Isolation** | Ingestion decoupled from downstream consumers. | **PASS** | Coaching engine consumes canonical domain models (`workout_sessions`, `strength_sets`, `personal_records`). |
| **III. Multimodal Ergonomics & Robustness** | Mobile-optimized interface; resilient to network glitches. | **PASS** | Web UI with fast status badges, responsive schedule viewer, and graceful error toasts. |
| **IV. Unified Volume Modeling & Peak Performance** | Consumes normalized metrics across endurance and strength. | **PASS** | Ingests Feature 003 aggregates (Zone 2 %, total volume load, Epley 1RM, and milestone PRs). |
| **V. Philosophy-Steered AI Coaching** | Decoupled user philosophies; planning and analysis modes. | **PASS** | Full implementation of Analysis Mode (critiques) and Planning Mode (schedules) steered by `CoachingPhilosophy`. |
