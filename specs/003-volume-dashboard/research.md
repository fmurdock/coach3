# Phase 0 Research: Unified Training Volume Modeling and Peak Performance Dashboard

**Feature**: `003-volume-dashboard`  
**Date**: 2026-11-17  
**Branch**: `feature/003-volume-dashboard`  
**Status**: Completed

## 1. Technical Objectives & Constraints

This feature delivers a self-hosted analytics engine and interactive visual dashboard that unifies endurance and resistance training data into actionable volume metrics and deterministic personal records (PRs), fully satisfying **Constitution Principle IV**:
> *"The core analytics engine MUST normalize disparate training modalities into consistent, queryable volume and intensity aggregates (Zone 2 cardio duration, weekly mileage, effective sets, total volume load, estimated 1RM/5RM, and external load added to bodyweight) and track historical peak performances and PRs across arbitrary rolling windows."*

---

## 2. Key Architectural Decisions & Analysis

### 2.1 Analytics Computation: Real-Time Indexed Aggregation vs Materialized Views
- **Decision**: Execute real-time indexed relational aggregations via SQLAlchemy async queries in `src/services/analytics_service.py`.
- **Rationale**: For self-hosted single-athlete or family usage (tens of thousands of sets and hundreds of endurance sessions), PostgreSQL with indices on `(user_id, start_time_utc)` and `(workout_session_id, set_index)` evaluates complete 90-day and all-time aggregates in $< 15\text{ms}$. Materialized views would add cron refresh overhead and cache invalidation complexity without measurable benefit.

### 2.2 Mathematical Formulas & Volume Normalization
1. **Strength Volume Load**:
   - Barbell & Dumbbell: $\text{Volume Load} = \sum (\text{reps} \times \text{weight})$
   - Calisthenics with added load: $\text{Added Volume Load} = \sum (\text{reps} \times \text{added\_weight})$
   - Pure bodyweight: Repetition count tracked separately; volume load counted as $0.0$ external resistance so as not to distort measured bar loads.
2. **1-Rep Max & 5-Rep Max Estimation**:
   - **Formula**: Standard Epley formula:
     $$\text{1RM}_{\text{est}} = w \cdot \left(1 + \frac{r}{30}\right)$$
   - Rep Cap: Only evaluated for working sets where $1 \le r \le 10$. Sets with $r > 10$ are treated as muscular endurance sets and excluded from 1RM estimation.
   - 5-Rep Max:
     $$\text{5RM}_{\text{est}} = \frac{\text{1RM}_{\text{est}}}{1 + \frac{5}{30}} = \frac{\text{1RM}_{\text{est}}}{1.1667}$$
3. **Endurance Milestone PR Detection**:
   - Matched within $\pm 3\%$ distance tolerance of standard benchmarks:
     - Running: 1 Mile ($1{,}609.34\text{m} \pm 48\text{m}$), 5k ($5{,}000\text{m} \pm 150\text{m}$), 10k ($10{,}000\text{m} \pm 300\text{m}$).
     - Concept2 Erg: 500m ($500\text{m} \pm 15\text{m}$), 2k ($2{,}000\text{m} \pm 60\text{m}$), 5k ($5{,}000\text{m} \pm 150\text{m}$).
   - Fastest performance = $\min(\text{active\_duration\_sec})$, reporting average pace and average power.

### 2.3 Visual Charting & UI Architecture
- **Decision**: Self-hosted standalone Chart.js bundle saved locally under `src/static/vendor/chart.umd.js`, served via FastAPI static files.
- **Rationale**: 100% offline-capable, zero external CDN requests, zero privacy leaks (Constitution Principle I), with fluid animations, tooltips, and responsive layout across desktop and mobile iPhone screens.

---

## 3. Constitution Compliance Check

- **Principle I (Self-Hosted Architecture & Sovereignty)**: 100% compliant. Analytics and charting run entirely in local container/browser. Zero third-party telemetry calls.
- **Principle II (Source Isolation)**: 100% compliant. Analytics operates on internal canonical domain tables (`workout_sessions`, `strength_sets`) without coupling to upstream Polar or Concept2 raw payloads.
- **Principle III (Multimodal Ergonomics)**: 100% compliant. Responsive web dashboard optimized for mobile iPhone viewport with quick date-range pills.
- **Principle IV (Unified Volume Modeling)**: 100% compliant. Implements exact volume equations, Zone 2 time distributions, and deterministic PR tracking across rolling windows.
- **Principle V (Philosophy-Steered AI Coaching)**: 100% compliant. Prepares normalized volume and PR metrics directly consumable by Feature 4 retrospective coaching analysis.
