# HiTeam Design System

## Design Direction

HiTeam is a campus operations product, not a decorative landing page. The current direction is a campus competition operations board: a black-and-white command rail, a white/light-blue workspace, and restrained blue status surfaces that borrow from Airtable's workflow clarity and Linear's surface discipline without copying any one brand.

## Audience Assumptions

Users are students and reviewers moving through practical workflows. They compare projects, deadlines, skill tags, award evidence, and application status. The design should support repeated decision-making over visual spectacle.

## Principles

- Prioritize task clarity over promotion.
- Keep density useful, not cramped.
- Make status obvious: recruiting, full, expired, applied, accepted, rejected.
- Keep actions close to the object they affect.
- Use copy that names the real campus scenario.
- Make demos self-explanatory through real data and visible state, not feature descriptions.

## Visual Tokens

Current CSS variables are the source of truth:

- Light canvas: `#f3f5f7`
- Light surface: `#ffffff`
- Light secondary surface: `#eef1f4`
- Dark canvas: `#07090c`
- Dark surface: `#0d1014`
- Text: `#18212b` / `#f5f7fa`
- Muted text: `#687480` / `#aab5c2`
- Primary blue: `#2563eb` / `#4f83e8`
- Radius: `10px`

Guidance:

- Keep black as the dark command surface and white/light blue as the primary light theme.
- Use blue for actions, focus, links, and matched states.
- Use borders and text for status distinction instead of a multicolor card palette.
- Avoid gradients, glassy neon surfaces, warm paper textures, and generic AI-product styling.
- Avoid cards inside cards. Cards are for repeated items, panels, dialogs, or framed tools.
- Use shadows sparingly; most hierarchy should come from spacing, borders, type, and state.

## Typography

The prototype uses local system CJK fonts:

```css
"Microsoft YaHei", "PingFang SC", "Segoe UI", Arial, sans-serif
```

Rules:

- Keep letter spacing at `0`.
- Use tabular numbers for counts, headcounts, and deadlines when adding numeric-heavy styles.
- Use compact headings inside panels; reserve large type for page-level titles only.
- Prefer sentence-like Chinese labels over marketing headlines.

## Layout

- Desktop: dark persistent command rail, sticky topbar, constrained content, mission brief, status deck, side filter plus list.
- Mobile: compact dark brand bar, sticky segmented navigation, single-column content, no fixed navigation covering form fields.
- Preserve stable dimensions for tag groups, action groups, filter controls, project suggestions, and mobile nav items.
- Avoid wide paragraphs in operational panels; lists and metadata should stay scannable.

Mission brief:

- The discover page starts with a real operational snapshot, not a marketing hero.
- Keep the copy tied to active competitions, deadlines, and team gaps.
- The dark board beside it should read as a live dispatch surface.

Task guide:

- The main information architecture is the five-step student flow: complete profile, find team, application progress, captain review, matched collaboration.
- Role switching is a mode control, not a page. It should reveal intent and hide irrelevant actions.
- Admin and file operations belong to the advanced tools drawer, never the primary path.

## Components

Recruitment cards:

- Show owner, program type, project title, linked competitions, campus/college, headcount, deadline, skill tags, and next action.
- Keep disabled states visually distinct for full or already-applied teams.
- Actions should be consistent: details, apply/status, owner controls where relevant.
- Use a left color stripe to make each row feel like a board item rather than a generic card.
- Include match explanations before asking the user to apply.

Forms:

- Inline validation is required for publish and import workflows.
- Do not rely only on toast messages.
- Place summaries before final submission when the workflow is high-risk.

Messages:

- Group by outcome and contact relevance.
- Contact release must visually depend on matching status.

Collaboration:

- Show only accepted matches; pending, rejected, expired, and unmatched teams must not appear here.
- Each match needs a clear counterpart, released contact card, next action, checklist, first-sync time, and local note.
- Keep collaboration files summarized here, but keep backup/import/reset controls in advanced tools.

Files:

- Always show import preview and validation result before state replacement.
- File rows need name, scope, type, size, time, and action state.

Admin:

- Moderation queues should show empty states, not blank panels.
- Approval/rejection actions must be visible and local to each pending item.

## Interaction

- Every button needs hover, active, disabled, and focus states.
- State changes should be immediate and visible.
- Toasts are for confirmation, not primary error handling.
- Keep motion minimal: opacity/transform transitions are acceptable; avoid bounce effects.
- Respect `prefers-reduced-motion` if adding animation.

## Accessibility

- Keep semantic sections, forms, labels, and buttons.
- Add a skip-to-content link before production handoff.
- Keep focus rings visible.
- Maintain WCAG AA contrast for text and controls.
- Ensure mobile controls remain reachable without being covered by fixed UI.

## Content Rules

- Use real HIT/campus/team-matching scenarios.
- Avoid generic names, generic product copy, and empty placeholder claims.
- Avoid "智能化平台", "一站式", "赋能", and similar vague wording unless the UI proves the claim.
- Success messages should be calm and direct.
- Error messages should tell the user what to fix.

## Screens To Audit Before Handoff

- Desktop discover list with filters open.
- Mobile discover list at 390px width.
- Publish form with validation errors.
- Publish form with draft summary and mobile action bar.
- Recruitment detail and application state.
- Applicant review with full-team boundary.
- Tagged profile, award short names, resume preview, and duplicate award hint.
- Messages after accepted/rejected applications.
- Matched collaboration with accepted contact card, checklist update, note save, and mobile layout.
- File import success and JSON parse failure.
- Admin pending and empty queues.
