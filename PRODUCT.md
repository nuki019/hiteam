# HiTeam Product Context

## Product Type

HiTeam is a local-first static prototype for a Harbin Institute of Technology student team-matching platform. It is currently a single-page HTML/CSS/JS app with browser `localStorage` persistence and JSON import/export.

## Users

- Students looking for competition teammates across campus, college, grade, skills, and availability.
- Team owners who need to publish recruitment posts, review applicants, and release contact details after matching.
- Prototype reviewers who need to see the full flow without a backend, account system, or deployment setup.
- Administrators reviewing tag requests, competition taxonomy, reports, and platform-level statistics.

## Product Purpose

The prototype should demonstrate a complete team-matching workflow:

1. Discover relevant recruitment posts.
2. Publish a structured recruitment request.
3. Build and export an ability profile.
4. Apply to teams and review applicants.
5. Receive result/contact notifications.
6. Continue after acceptance in a matched collaboration workspace.
7. Manage local files and full JSON backups.
8. Inspect admin moderation and taxonomy flows.

The target is not a marketing landing page. It should feel like a practical campus operations tool: dense enough for repeated use, clear enough for demo review, and polished enough to communicate product intent.

## Current Scope

Implemented:

- Multi-view static app: discover, publish, profile, mine, messages, collaboration, admin, files.
- Five-step task guide: profile readiness, team discovery, application progress, captain review, matched collaboration.
- Lightweight role switch for applicant, captain, system admin, and platform creator modes.
- Local demo data with expiry, matching, application, approval, rejection, messages, and file records.
- Match explanations with skill tags, missing skills, year eligibility, locality, reusable competitions, slots, and deadline risk.
- Searchable project source with existing-project/new-project selection, annual-project and innovation-training program rules, and one-way project-to-competition reuse links.
- Matched collaboration workspace with accepted-match cards, contact copy, first-sync time, local notes, checklist progress, and collaboration-file summary.
- Publish validation, draft saving, publish summary, program-aware grade ranges, tag checks, SMS/captcha simulation, and attachment intake.
- Ability profile with award short names, skill tags, resume preview dialog, duplicate hints, avatar/file export, and profile export.
- Creator-only administrator appointment/revocation with local audit records.
- File management with full JSON export/import, local library records, downloads for small files, reset, and clear-data controls.
- Advanced tools drawer for admin, file, backup, import, and reset flows.
- Responsive layout with desktop sidebar, mobile segmented navigation, and 390px no-overflow checks.

Out of scope for the static prototype:

- Real authentication.
- Real SMS/captcha verification.
- Server-side storage.
- Secure upload scanning.
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
