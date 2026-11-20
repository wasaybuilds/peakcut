---
version: 1
slug: "frontend-app-page-tsx"
primary_target: "frontend/app/page.tsx"
related_targets: ["frontend/app/jobs/[id]/page.tsx","frontend/app/settings/page.tsx","frontend/components/post-dialog.tsx","frontend/components/layout-panel.tsx"]
---

## Scope

PeakCut web app (Operate mode): home (new video + recent jobs), job page (progress, layout + face cam editor, clip grid, posting), settings (accounts), post dialog. Audience: solo clippers on laptops, often at night, reviewing video for long sessions; both fast volume and careful review.

## Direction contract

THESIS: Every video is billed on a cinema marquee: its title set in push-in letter tiles on grooved black felt, its progress a bulb chase. Refuses the category default of a near-black SaaS dashboard with purple gradients and soft rounded cards.

OWN-WORLD: Grooved felt black (#0d0c0b) shell, warm letter white (#f4efe6) ink, bulb amber (#ffb43d) only for live progress, red (#e5484d) only for failure, green (#7fd6a1) only for posted. Big Shoulders Display/Text, one condensed family, rank by weight and case. One radius (4px), one-device-pixel rules. Clip states as one mark in a fixed cell: filled posted, hollow queued, struck failed.

STORY: The clipper sees what is playing now and how far along it is, scans clips by score, reviews or fixes one, and posts. Nothing hides; every failure says what to do.

FIRST VIEWPORT: Left rail (brand, New video, jobs with live %, accounts). Main: letterboard title block with the video's title as letter tiles, details line and bulb-chase progress beneath; then a toolbar (clip count, layout segmented control, Write captions) and a 5-up 9:16 clip grid with score plate, title, state mark and Post.

FORM: Marquee Letterboard, position 6 of 7 on the grounded list; seed:2a22120201114410. Signature move: bulb-chase progress; letter tiles set the title once per job.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
