# Research & Technical Decisions: Integration Configuration & Workflow Stabilization

**Feature**: `005-integration-config-workflow`  
**Date**: 2026-11-18  
**Status**: Completed  

---

## 1. Credential Persistence & Dynamic Resolution

### Problem
Previously, Polar and Concept2 API client credentials (`CLIENT_ID`, `CLIENT_SECRET`, `REDIRECT_URI`) were read statically from environment variables in `src/core/config.py`. Athletes configuring the system via self-hosted containers or browsers could not update credentials without terminal access and container restarts.

### Technical Decision
1. **Database-First with Environment Fallback**:
   - Create table `integration_client_configs` in PostgreSQL storing encrypted credentials per provider (`polar`, `concept2`).
   - Use existing AES/Fernet encryption from `src.core.security` (`encrypt_token`, `decrypt_token`) with `settings.ENCRYPTION_KEY`.
   - Provide a service helper `get_provider_credentials(provider: str, db: AsyncSession)`:
     - Check `integration_client_configs` first.
     - If empty or not configured, fallback to `settings.POLAR_CLIENT_ID` / `settings.CONCEPT2_CLIENT_ID`.
2. **Security**:
   - Mask secrets when sending back to the UI (e.g. `Client Secret: ••••••••••••abcd`).
   - Allow updating without re-entering the secret if unchanged.

---

## 2. OAuth Callback & Redirect Architecture

### Problem
Polar AccessLink and Concept2 OAuth 2.0 flows redirect the user's browser via HTTP `GET` with query parameters `?code={code}&state={state}` (or `?error={error}&error_description={desc}`). The existing backend only had a JSON `POST /exchange-code` endpoint, requiring manual or client-side fragment extraction which was fragile across mobile Safari and desktop browsers.

### Technical Decision
1. **Dedicated GET Callback Route**:
   - Implement `GET /api/v1/integrations/{provider}/callback` in FastAPI.
   - Handle provider error responses: redirect to `/config?status=error&provider={provider}&message={error_description}`.
   - On valid `code`:
     - Resolve provider credentials from database or `.env`.
     - Perform code exchange via `PolarAdapter` / `Concept2Adapter`.
     - Persist or update `IntegrationAccount` with encrypted tokens and external user ID.
     - Redirect to `/config?status=connected&provider={provider}`.
2. **Dynamic Redirect URI in Setup Guide**:
   - The setup guide on `/config` dynamically computes the exact callback URL using `window.location.origin + '/api/v1/integrations/' + provider + '/callback'`.
   - Provides a one-click "Copy Callback URL" button for easy pasting into Polar Flow (`flow.polar.com`) and Concept2 (`log.concept2.com`) developer portals.

---

## 3. Integration Diagnostic & Verification Contract

### Problem
Athletes had no way to verify whether their credentials and tokens were still valid or if an account was actively synchronizing.

### Technical Decision
Implement `POST /api/v1/integrations/{provider}/verify`:
1. **Polar Verification Protocol**:
   - Call Polar AccessLink `GET https://polarremote.com/v2/users/{user-id}` (or transaction registration check).
   - If token expired (HTTP 401), trigger token refresh using stored refresh token.
   - Extract athlete identifier and registration status.
2. **Concept2 Verification Protocol**:
   - Call Concept2 Logbook API `GET https://log.concept2.com/api/users/me`.
   - If token expired, refresh using `Concept2Adapter.refresh_token()`.
   - Extract username, email (anonymized), and logbook user ID.
3. **Response Schema**:
   ```json
   {
     "provider": "polar",
     "is_connected": true,
     "status": "healthy",
     "athlete_name": "Athlete #109283",
     "expires_at": "2026-12-18T20:00:00Z",
     "last_sync_at": "2026-11-18T19:30:00Z",
     "error_message": null
   }
   ```

---

## 4. Universal Responsive Navigation Shell

### Problem
The application currently consists of isolated HTML pages (`/gym`, `/dashboard`, `/coach`) with no shared navigation or way to switch contexts.

### Technical Decision
1. **Shared Navbar Layout**:
   - Standardize a responsive HTML/CSS top navigation bar embedded into:
     - `src/static/gym.html` (Gym Voice Logger)
     - `src/static/dashboard.html` (Volume & PRs Dashboard)
     - `src/static/coach.html` (Adaptive AI Coaching)
     - `src/static/config.html` (Settings, Integrations & Setup)
2. **Consistent Visual Language**:
   - Dark theme styling matching Coach3's aesthetic (`#0f172a` slate background, `#3b82f6` accents, `#10b981` success badges).
   - Route highlighting based on `window.location.pathname`.
   - Mobile hamburger / compact pill layout for mobile Safari.

---

## 5. Demo Data Seeding & Clean Isolation

### Problem
Empty databases render blank graphs on `/dashboard` and empty critique candidates on `/coach`, making first-time verification and debugging difficult.

### Technical Decision
1. **Isolated Demo Tagging**:
   - Add `is_demo: bool = Column(Boolean, default=False, nullable=False)` to `workout_sessions`.
   - Seed script creates:
     - 1 Default Athlete Profile (`User` with HR max 185, resting HR 50).
     - 1 Active Coaching Philosophy (Polarized 80/20).
     - 3 Outdoor Running sessions with 5-zone HR distributions and GPS polylines.
     - 2 Concept2 Indoor Rowing sessions (5k steady state Zone 2 and 5x500m interval splits).
     - 2 Gym Strength sessions with Bench Press, Weighted Pull-ups, and Barbell Squats.
2. **Clean Reset Guarantee**:
   - `DELETE /api/v1/admin/demo` deletes ONLY records where `is_demo == True`, completely preserving user credentials, integration accounts, and real workout telemetry.
