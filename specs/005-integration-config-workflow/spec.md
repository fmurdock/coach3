# Feature Specification: Integration, Configuration Screen & Workflow Stabilization

**Feature Branch**: `feature/005-integration-config-workflow`  
**Created**: 2026-11-18  
**Status**: Specified  
**Input**: User description: "Integration, configuration screen with setup guide for Polar and Concept2 credentials/connection verification, cross-module navigation, seed demo data, and bug triage."

## Clarifications

### Session 2026-11-18
- Q: How should the Polar and Concept2 developer credentials (Client ID and Client Secret) entered in the configuration screen be persisted? → A: Option A — Encrypted in the database with fallback to `.env`.
- Q: When verifying an integration connection in the configuration screen, what diagnostic information should the system validate and display? → A: Option A — Full profile & token ping (test API, auto-refresh token if expired, display athlete name, status badge, and last sync timestamp).
- Q: How should the OAuth callback and redirect flow for Polar and Concept2 return the user to the configuration screen? → A: Option A — Backend callback with frontend redirect (`/api/v1/integrations/{provider}/callback` exchanges code, saves tokens, and redirects to `/config?status=connected&provider={provider}`; setup guide shows the exact callback URL).
- Q: How should the sample workout seeding and demo data workflow be triggered? → A: Option A — Both UI action on `/config` ("Load Sample Workouts" and "Reset Demo Data") and CLI script (`python -m src.scripts.seed_demo`).
- Q: Should the new configuration screen also centralize AI model/LLM provider settings alongside Polar and Concept2? → A: Option A — Unified Settings Hub (centralize Polar, Concept2, and LLM provider credentials in `/config`, with active model selection still accessible on `/coach`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Guided Configuration & Integration Setup (Priority: P1) 🎯 MVP

As an athlete setting up Coach3, I want a dedicated configuration screen with a step-by-step setup guide where I can input my Polar AccessLink and Concept2 credentials, initiate connection/authorization, and verify active connectivity, so that my endurance workouts synchronize into Coach3 without manually editing raw `.env` files.

**Why this priority**: Without verified credentials and functional OAuth connections, Polar and Concept2 ingestion cannot occur, leaving the volume dashboard and AI coach without real training data.

**Independent Test**: Navigate to `/config`, input client credentials, click Connect to complete OAuth, and click Verify Connection to observe green connectivity status, athlete name, and audit logging.

**Acceptance Scenarios**:
1. **Given** a user on `/config`, **When** they view the Polar or Concept2 setup guide, **Then** they see step-by-step instructions, a copyable OAuth Redirect URI (`/api/v1/integrations/{provider}/callback`), and input fields for Client ID and Client Secret.
2. **Given** credentials entered in the UI, **When** saved, **Then** the credentials are encrypted with `ENCRYPTION_KEY` and saved in the database, with automatic fallback to `.env` variables if unset in DB.
3. **Given** valid credentials, **When** the user clicks "Connect", **Then** the browser navigates to the provider's OAuth consent screen; upon approval, the provider redirects to the backend callback, which exchanges the authorization code, stores encrypted tokens per Constitution Principle I, and redirects the user back to `/config?status=connected&provider={provider}` with a success notification.
4. **Given** an existing connection, **When** the user clicks "Verify Connection", **Then** the system pings the provider API, auto-refreshes expired tokens, and displays athlete display name, connection health status badge (Active/Expired/Error), token expiration window, and last sync timestamp.
5. **Given** a connected provider on `/config` or `/dashboard`, **When** the user clicks "Sync Now", **Then** the system triggers an immediate manual workout sync via `POST /api/v1/integrations/{provider}/sync`, reporting imported/updated workout counts and refreshing the last sync timestamp.

---

### User Story 2 - Unified Settings Hub for AI & Integrations (Priority: P1)

As an athlete configuring Coach3, I want the Configuration screen to centralize my AI Inference Provider settings (Google Gemini API key or local `llama.cpp` endpoint) alongside my equipment integrations, so that all third-party services and AI credentials can be managed and verified in a single place.

**Why this priority**: Eliminates confusion about where credentials belong; athletes can configure and test both telemetry providers and AI models in one settings hub.

**Independent Test**: Configure a Gemini API key or local llama.cpp endpoint on `/config`, click "Test AI Connection", and verify that the active provider status updates across `/config` and `/coach`.

**Acceptance Scenarios**:
1. **Given** the `/config` screen, **When** viewing the AI Inference Provider section, **Then** the user can configure Gemini API keys or local `llama.cpp` URLs, select active status, and trigger a test inference ping.
2. **Given** active AI settings updated in `/config`, **When** the user navigates to `/coach`, **Then** the AI coaching interface immediately reflects the active provider without re-prompting.

---

### User Story 3 - Cross-Module Navigation & Unified Shell (Priority: P1)

As an athlete using Coach3 on mobile or desktop, I want a unified navigation bar across all views (Gym Voice Logger, Volume Dashboard, AI Coach, Configuration), so that I can switch contexts effortlessly without changing URLs manually.

**Why this priority**: Currently, `/gym`, `/dashboard`, and `/coach` exist as disconnected standalone pages with no navigation bar linking them.

**Independent Test**: Load any page (`/gym`, `/dashboard`, `/coach`, `/config`) and navigate between all four views with a single click or tap.

**Acceptance Scenarios**:
1. **Given** any screen in the Coach3 application, **When** viewed on mobile or desktop, **Then** a persistent, responsive navigation header allows direct navigation to Gym (`/gym`), Dashboard (`/dashboard`), Coach (`/coach`), and Settings (`/config`).
2. **Given** a workout logged in Gym mode, **When** navigating to Dashboard or Coach, **Then** the new workout immediately reflects in volume totals and critique candidates without requiring a manual page reload.

---

### User Story 4 - Local Demo Seed & Environment Resilience (Priority: P2)

As a developer or new athlete, I want a one-click or single-command demo seed workflow that populates realistic athletes, training philosophies, and sample workouts (runs, rows, strength), so that all dashboards and coach critiques render meaningful data immediately.

**Why this priority**: Empty-state databases cause confusing errors and blank charts for new users exploring the system.

**Independent Test**: Click "Load Sample Workouts" on `/config` or run `python -m src.scripts.seed_demo`, then verify all charts on `/dashboard` and critiques on `/coach` render populated data.

**Acceptance Scenarios**:
1. **Given** an empty database, **When** the user clicks "Load Sample Workouts" on `/config` or executes `python -m src.scripts.seed_demo`, **Then** the system creates sample outdoor runs (with Zone 2 heart rate data), erg rowing sessions, and strength workouts.
2. **Given** sample data loaded, **When** navigating to `/dashboard`, **Then** weekly mileage, Zone 2 hours, and PR calculations display valid figures and graphs.
3. **Given** the user wants to start clean, **When** clicking "Reset Demo Data", **Then** only synthetic demo records are purged while preserving real user accounts and integration credentials.

---

### User Story 5 - Bug Triage & Graceful Error Handling (Priority: P2)

As an athlete, when an external API (Polar, Concept2, Gemini, local llama.cpp) is down, throttled, or unconfigured, I want clear, human-readable error toasts in the UI instead of silent failures or raw stack traces.

**Why this priority**: Eliminates unhandled runtime bugs and communicates clearly when external dependencies fail.

**Acceptance Scenarios**:
1. **Given** an unconfigured or failing external service, **When** an action is triggered in the UI, **Then** a visible toast/banner explains the issue and links directly to `/config` to resolve it.

---

## Edge Cases

- User inputs invalid or expired Polar/Concept2 client secret.
- Local network dropouts occur while completing OAuth redirect.
- Encryption key is missing from environment when saving tokens.
- Dual-engine LLM endpoint is unreachable during coach setup.
- Database contains credentials but `.env` also has values (DB takes precedence over `.env`).
- Provider token is expired during verification (system attempts refresh; if refresh token is revoked, marks status Expired with re-auth prompt).
- OAuth callback error parameters (e.g. `?error=access_denied`) received from provider (system redirects to `/config?status=error&message=...` and displays human-readable alert).
- User attempts to seed demo data twice (system detects existing demo tags and is idempotent, avoiding duplicate workouts per Constitution Principle II).
- Polar AccessLink OAuth requires explicit `scope=accesslink.read_all` and exact character-for-character matching with registered developer portal redirect URIs.
- OAuth authorization query parameters MUST use clean URL encoding to prevent key duplication or malformed query strings.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a dedicated Configuration UI (`/config`) accessible from the main navigation.
- **FR-002**: Configuration UI MUST provide dedicated setup cards for Polar AccessLink and Concept2 Logbook with step-by-step guidance and dynamic copyable redirect URIs.
- **FR-003**: System MUST persist integration client credentials (Client ID, Client Secret) encrypted in the database using `ENCRYPTION_KEY`, with fallback to `.env` variables.
- **FR-004**: System MUST provide a "Verify Connection" diagnostic action that pings the provider API, auto-refreshes expired tokens, and returns athlete identity/display name, connection health status badge, token expiration window, and last sync timestamp.
- **FR-005**: Backend MUST provide GET `/api/v1/integrations/{provider}/callback` to handle authorization code redirects, store tokens, and redirect back to `/config`.
- **FR-006**: Configuration UI MUST centralize AI Inference Provider management (Gemini API key and local `llama.cpp` configuration) with connection health testing.
- **FR-007**: All web interfaces (`/gym`, `/dashboard`, `/coach`, `/config`) MUST include a consistent responsive navigation bar with active route highlighting.
- **FR-008**: System MUST provide both a UI card on `/config` ("Load Sample Workouts" / "Reset Demo Data") and a CLI command (`python -m src.scripts.seed_demo`) to populate realistic sample athletes, philosophies, endurance runs, rowing sessions, and strength logs.
- **FR-009**: Configuration UI and Volume Dashboard MUST provide an on-demand "Sync Now" trigger executing immediate provider synchronization (`POST /api/v1/integrations/{provider}/sync`) with real-time feedback.

### Key Entities

- **Integration Client Config**: Stores encrypted OAuth client credentials (client ID, client secret) per provider (Polar, Concept2).
- **Integration Account**: Existing model storing encrypted access tokens, refresh tokens, scopes, and external user IDs.
- **Sync Audit Log**: Records synchronization runs, status (success, error), and affected items.
- **Workout Session**: Canonical workout session tagged as either real athlete telemetry or demo/sample data.
- **Demo Seed Bundle**: Collection of pre-configured sample entities (philosophies, Polar running sessions with HR zones, Concept2 erg sessions, gym strength logs).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero-Terminal Setup: A new user can complete Polar and Concept2 credential configuration and connection verification entirely through the browser within 3 minutes of opening `/config`.
- **SC-002**: Verification Latency: Integration connection health check returns full diagnostic results (identity, token status, last sync) in under 2 seconds.
- **SC-003**: Navigation Parity: 100% of screens (`/gym`, `/dashboard`, `/coach`, `/config`) display the unified navigation bar with zero broken links.
- **SC-004**: Instant Demo Onboarding: Clicking "Load Sample Workouts" seeds realistic data across running, rowing, and strength in under 3 seconds, populating volume charts and AI critique candidates.
- **SC-005**: Error Visibility: 100% of failed API calls (external OAuth, LLM endpoints, sync drops) surface actionable user-facing messages rather than blank states or uncaught browser console errors.

## Assumptions & Dependencies

- Application is hosted on user-controlled hardware (macOS / Linux / Docker) with an accessible HTTP host/port.
- User registers developer apps on Polar Flow (`flow.polar.com`) and Concept2 (`log.concept2.com`) to obtain Client ID and Client Secret.
- Encryption key (`ENCRYPTION_KEY`) is set in the environment or generated during installation for cryptographic security.
- Modern browser (Safari on iOS / Chrome on desktop) with HTML5/CSS and fetch API support.
