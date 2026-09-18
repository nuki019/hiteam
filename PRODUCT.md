# HiTeam Product Context

## Product Type

HiTeam is a single-page HTML/CSS/JS application for Harbin Institute of Technology student team matching. The current prototype includes a dependency-free Python/SQLite backend for authentication and shared business data; browser `localStorage` is retained only for UI preferences, local attachments, and JSON backup data.

## Users

- Students looking for competition teammates across campus, college, grade, skills, and availability.
- Team owners who need to publish recruitment posts, review applicants, and release contact details after matching.
- Prototype reviewers who need to inspect the full flow with a small local backend and reproducible startup script.
- Administrators reviewing tag requests, competition taxonomy, reports, and platform-level statistics.

## Product Purpose

The prototype should demonstrate a complete team-matching workflow:

1. Discover relevant recruitment posts.
2. Publish a structured recruitment request.
3. Build and export an ability profile.
4. Apply to teams and review applicants.
5. Receive result/contact notifications.
6. Receive the result and released contact information after review; teams create their own group chat.
7. Manage local files and full JSON backups.
8. Inspect admin moderation and taxonomy flows.

The target is not a marketing landing page. It should feel like a practical campus operations tool: dense enough for repeated use, clear enough for demo review, and polished enough to communicate product intent.

## Current Scope

Implemented:

- Multi-view app: discover, publish, profile, mine, messages, admin, and files.
- Four-step task guide: profile readiness, team discovery, application progress, and captain review.
- Lightweight role switch for applicant, captain, system admin, and platform creator modes.
- Backend-backed user accounts with expiry, matching, application, approval, rejection, messages, and draft records.
- Match explanations with skill tags, missing skills, year eligibility, locality, reusable competitions, slots, and deadline risk.
- Searchable project source with existing-project/new-project selection, annual-project and innovation-training program rules, and one-way project-to-competition reuse links.
- Publish validation, draft saving, publish summary, program-aware grade ranges, tag checks, SMS/captcha simulation, and attachment intake.
- Ability profile with award short names, skill tags, resume preview dialog, duplicate hints, avatar/file export, and profile export.
- Creator-only administrator appointment/revocation with server-side audit records.
- File management with full JSON snapshot export, local-cache import, local library records, downloads for small files, reset, and clear-cache controls.
- Advanced tools drawer for admin, file, backup, import, and reset flows.
- Responsive layout with desktop sidebar, mobile segmented navigation, and 390px no-overflow checks.

Out of scope for the current prototype:

- Production-grade authentication and unified identity integration.
- Real SMS/captcha verification.
- Server-side binary file storage and upload scanning.
- Cross-user real-time messaging.
- Production privacy/legal enforcement.

## Quality Bar

A change is considered complete only when:

- `node --check assets/app.js` passes.
- The app loads on `http://127.0.0.1:8765/index.html`.
- Desktop and mobile screenshots show no broken layout or incoherent overlap.
- Primary flows still work: filter, publish, apply/review, tagged resume preview, files export/import, and role governance.
- New UI copy is specific to HIT student team matching, not generic SaaS language.

## Next Optimization Priorities

1. Add composed empty states for filters, drafts, files, and admin queues.
2. Add import conflict handling instead of replacing state immediately after JSON validation.
3. Add a small test harness for deterministic UI smoke checks.
