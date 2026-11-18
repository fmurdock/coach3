# Feature Specification: Gym Mode Natural Language Workout Logging

**Feature Branch**: `feature/002-gym-voice-logging`

**Created**: 2026-11-17

**Status**: Draft

**Input**: User description: "Gym Mode natural language workout logging: iPhone voice entry and parsing for strength and calisthenic workouts, extracting compound lifts and bodyweight movements with added load (e.g. '5 sets by 8 reps of backsquat at 185 pounds' or '3 sets of 12 pullups with an extra 30 pounds added'), producing structured sets and reps for instant validation before persisting to the database."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Voice Logging for Compound Lifts with Instant Confirmation (Priority: P1)

An athlete training in the gym speaks a compound strength set into their iPhone between sets (e.g., "5 sets by 8 reps of back squat at 185 pounds" or "bench press 3 sets of 5 at 225"). The system extracts the canonical exercise name, set count, rep count, weight, and unit, and returns a structured preview for one-tap confirmation before writing to the database.

**Why this priority**: Compound resistance movements form the backbone of strength training. In-gym logging must be fast and error-free without manual number typing while fatigued.

**Independent Test**: Can be tested independently by submitting raw spoken text (or audio) containing compound lift statements, verifying that parsed exercise, sets, reps, weight, and unit match expected values, and confirming persistence creates a verified workout session and strength sets.

**Acceptance Scenarios**:
1. **Given** an athlete in an active gym session, **When** they speak or dictate "5 sets by 8 reps of back squat at 185 pounds", **Then** the system parses this into 5 individual completed sets of Back Squat at 8 reps with 185 lbs and presents a staged confirmation preview.
2. **Given** a staged parsed set preview, **When** the athlete confirms or edits the values and taps persist, **Then** the sets are committed to the database under the current workout session.
3. **Given** a spoken phrase with shorthand weight such as "3 sets of 5 at 225 on bench", **Then** the system correctly attributes 225 lbs to Bench Press for 3 sets of 5 reps.

---

### User Story 2 - Calisthenic and Weighted Bodyweight Movement Logging (Priority: P1)

An athlete performs bodyweight calisthenics (e.g., pull-ups, dips, push-ups) with or without added external resistance (e.g., "3 sets of 12 pullups with an extra 30 pounds added" or "4 sets of 15 bodyweight pushups"). The system isolates the movement type, recognizes it as bodyweight, and captures the added load distinctly from external-only barbell/dumbbell loads.

**Why this priority**: Calisthenic progression relies on separating athlete bodyweight from external weight belts/vests to accurately model total work and overload.

**Independent Test**: Can be tested by parsing phrases referencing bodyweight movements with positive added load, zero added load, or assisted load, verifying the structured sets distinguish `is_bodyweight` and `added_weight`.

**Acceptance Scenarios**:
1. **Given** an athlete speaking "3 sets of 12 pullups with an extra 30 pounds added", **When** processed, **Then** the system identifies the exercise as Pull-Up, sets `is_bodyweight` to true, reps to 12, added load to 30 lbs, and set count to 3.
2. **Given** an athlete speaking "4 sets of 15 pushups bodyweight only", **When** processed, **Then** the system records 4 sets of 15 reps with 0 lbs added load and flags the exercise as bodyweight.
3. **Given** an athlete speaking "3 sets of 8 assisted dips minus 20 pounds", **When** processed, **Then** the system flags the movement as assisted bodyweight with a 20 lb counterbalance.

---

### User Story 3 - Perceived Exertion (RPE) and Rest Interval Capture (Priority: P2)

An athlete speaks supplementary set context alongside reps and weights, including Rate of Perceived Exertion (RPE / RIR) and rest duration (e.g., "did a heavy single at 315 on deadlift, felt like RPE 9, 3 minutes rest"). The system records exertion metrics alongside the primary work sets.

**Why this priority**: RPE and rest duration allow fatigue tracking and auto-regulation in advanced strength philosophies.

**Independent Test**: Can be tested by feeding phrases containing explicit RPE values (1-10 or "reps in reserve") and rest intervals into the parser and checking that the structured set captures `rpe` and `rest_seconds`.

**Acceptance Scenarios**:
1. **Given** a spoken phrase "1 rep at 315 on deadlift at RPE 8.5", **When** processed, **Then** the structured set contains 1 set, 1 rep, 315 lbs, and RPE 8.5.
2. **Given** a spoken phrase with "2 reps in reserve", **When** processed, **Then** the system converts 2 RIR into RPE 8.0.

---

### User Story 4 - Multi-Set or Multi-Exercise Batch Dictation (Priority: P3)

An athlete dictates an entire complex or circuit after completion (e.g., "I just did 3 sets of 10 dumbbell lunges with 50s, followed by 3 sets of 15 calf raises"). The system parses the compound sentence into ordered, separate exercises with their respective sets.

**Why this priority**: Athletes often prefer speaking once at the end of a round or superset rather than logging after every individual set.

**Independent Test**: Can be tested by providing compound sentences containing multiple distinct exercise clauses and verifying separate exercise groupings are generated in chronological order.

**Acceptance Scenarios**:
1. **Given** a multi-exercise dictation, **When** processed, **Then** the system produces discrete structured groups for each exercise mentioned without mixing reps or loads between them.

---

### Edge Cases

- **Colloquial Weight / Plate Math**: Athletes saying "two plates" (225 lbs / 100 kg), "a plate and a 25", or "the bar" (45 lbs / 20 kg). The system should recognize common barbell vernacular or prompt for explicit weight if ambiguous.
- **Ambiguous Exercise Names**: Saying "press" could mean barbell overhead press, dumbbell shoulder press, leg press, or bench press. The system should present candidate matches with high-confidence defaults based on past user history.
- **Fatigued / Slurred Speech & Background Gym Clatter**: Heavy breathing, dropped barbells, or background gym music distorting transcription. The system must display the raw transcript side-by-side with parsed fields so the athlete immediately spots transcription inaccuracies.
- **Unit Discrepancies**: Athlete switches between pounds and kilograms, or fails to state the unit (e.g., "squatted 185"). System defaults to user profile default unit (e.g., lbs) unless explicitly stated.
- **Warmup vs Working Sets**: Athlete mentions "warmup set of 10 at 135, then 3 working sets of 5 at 225". System must flag warmup sets so analytics do not skew effective volume.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept natural language workout descriptions as text transcripts generated client-side from mobile devices (e.g., iPhone iOS native speech dictation or Web Speech API).
- **FR-002**: System MUST process client-side transcribed text through a dedicated natural language parsing engine without requiring server-side raw audio processing or GPU infrastructure.
- **FR-003**: System MUST extract structured workout components from natural language: canonical exercise name, number of sets, repetitions per set, resistance weight, unit of weight, bodyweight indicator, added/assisted load, and optional RPE.
- **FR-004**: System MUST standardize spoken exercise names against a strict pre-defined exercise dictionary with aliases; if a spoken exercise cannot be resolved to an allowed dictionary entry, the system MUST flag the movement as unrecognized and prompt the athlete to select a recognized movement.
- **FR-005**: System MUST differentiate bodyweight movements (pull-ups, chin-ups, dips, push-ups) from external load movements (barbell squat, dumbbell bench), recording external weight as `added_weight` or `counterweight` relative to bodyweight.
- **FR-006**: System MUST return an intermediate, staged validation representation to the mobile client displaying parsed exercise, sets, reps, weight, and confidence score before persisting.
- **FR-007**: System MUST enforce an explicit confirmation step for every parsed log: presenting a staged review card on the mobile UI with exercise, sets, reps, and load, allowing one-tap confirmation or inline adjustment before persisting.
- **FR-008**: System MUST allow the athlete to edit or correct any parsed field (exercise name, reps, weight) on the mobile client before persisting.
- **FR-009**: System MUST persist confirmed sets into the relational database linked to a `workout_sessions` record with `sport_type = 'strength'`.
- **FR-010**: System MUST associate each confirmed set with timestamp, set index/sequence, target reps, completed reps, load, and warm-up vs working set classification.
- **FR-011**: System MUST enforce idempotency on set submissions to prevent accidental double-logging if an athlete taps confirm multiple times.
- **FR-012**: System MUST preserve the original raw voice transcript and parsed confidence metadata for auditability and parser improvement.

### Key Entities *(include if feature involves data)*

- **StrengthExercise**: Master definition of an exercise movement (name, canonical code, primary muscle group, category: barbell/dumbbell/machine/bodyweight, default weight unit).
- **ExerciseAlias**: Synonyms and colloquial phrases mapping to canonical `StrengthExercise` (e.g., "squats", "back squats", "high bar squat" -> Back Squat).
- **StrengthSet**: Discrete logged set belonging to a `workout_session` (set number, exercise ID, reps completed, weight value, weight unit, is_bodyweight, added_weight, rpe, is_warmup, completed_at).
- **VoiceTranscriptionLog**: Audit record linking raw audio/transcript, structured parsing result, model confidence, and final confirmed edits.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Athletes can log a strength set via voice from microphone tap to confirmed database write in under 4 seconds on mobile.
- **SC-002**: Natural language parsing achieves at least 92% first-pass accuracy on standard compound lift descriptions ("N sets of R reps at W lbs/kgs").
- **SC-003**: 100% of bodyweight exercises with added load (e.g., weighted pull-ups) correctly isolate added resistance without overwriting total load.
- **SC-004**: Zero accidental duplicate sets created during poor cellular connection or rapid double-tap on mobile.
- **SC-005**: Athletes can view and edit any parsed field with a single tap before final database commit.

---

## Assumptions

- **Mobile Client**: The primary input device is an iPhone accessing a mobile-optimized web UI (PWA or responsive web page).
- **Language**: Voice logging will initially be conducted in English.
- **Default Units**: If an athlete does not specify "pounds" or "kilos", the system assumes their configured profile default unit (default: pounds).
- **Hardware Integration**: Real-time microphone audio capture uses standard browser MediaRecorder or native iOS speech-to-text dictation.
- **Session Continuity**: If an active strength workout session is open on the user's dashboard, new voice logs automatically append to that open session; if none is open, a new strength session is initialized.
