---
name: PeakCut
description: Every video billed on a cinema marquee; long streams in, captioned 9:16 clips out.
colors:
  felt: "#0d0c0b"
  felt-rail: "#100f0d"
  felt-raised: "#141210"
  felt-high: "#1c1a17"
  groove: "#090807"
  line: "#2a2724"
  line-strong: "#3d3933"
  ink: "#f4efe6"
  ink-soft: "#c9c1b4"
  ink-mute: "#958d81"
  bulb: "#ffb43d"
  bulb-dim: "#3a3127"
  fail: "#e5484d"
  posted: "#7fd6a1"
typography:
  display:
    fontFamily: "Big Shoulders, Arial Narrow, sans-serif"
    fontSize: "clamp(28px, 3.4vw, 46px)"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "0.01em"
    fontVariation: "opsz auto"
  headline:
    fontFamily: "Big Shoulders, Arial Narrow, sans-serif"
    fontSize: "24px"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "0.04em"
  title:
    fontFamily: "Big Shoulders, Arial Narrow, sans-serif"
    fontSize: "19px"
    fontWeight: 700
    lineHeight: 1.15
  body:
    fontFamily: "Big Shoulders, Arial Narrow, sans-serif"
    fontSize: "17px"
    fontWeight: 400
    lineHeight: 1.45
  body-small:
    fontFamily: "Big Shoulders, Arial Narrow, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.375
  button:
    fontFamily: "Big Shoulders, Arial Narrow, sans-serif"
    fontSize: "15px"
    fontWeight: 700
    letterSpacing: "0.1em"
  label:
    fontFamily: "Big Shoulders, Arial Narrow, sans-serif"
    fontSize: "13px"
    fontWeight: 600
    letterSpacing: "0.16em"
  score:
    fontFamily: "Big Shoulders, Arial Narrow, sans-serif"
    fontSize: "26px"
    fontWeight: 900
    lineHeight: 1
    fontFeature: "tnum"
rounded:
  tile: "2px"
  board: "4px"
  round: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  2xl: "32px"
  3xl: "40px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.felt}"
    typography: "{typography.button}"
    rounded: "{rounded.board}"
    padding: "0 16px"
    height: "40px"
  button-primary-hover:
    backgroundColor: "#fffaf1"
  button-primary-disabled:
    backgroundColor: "transparent"
    textColor: "{colors.ink-mute}"
  button-line:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.button}"
    rounded: "{rounded.board}"
    padding: "0 16px"
    height: "40px"
  button-line-hover:
    backgroundColor: "{colors.felt-high}"
  button-sm:
    padding: "0 12px"
    height: "32px"
  field:
    backgroundColor: "{colors.groove}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.board}"
    padding: "10px 14px"
    height: "44px"
  letter-tile:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.felt}"
    typography: "{typography.display}"
    rounded: "{rounded.tile}"
    padding: "0.02em 0.22em 0.04em"
  score-plate:
    backgroundColor: "{colors.felt}"
    textColor: "{colors.ink}"
    typography: "{typography.score}"
    rounded: "{rounded.tile}"
    padding: "2px 8px"
  title-board:
    backgroundColor: "{colors.felt-raised}"
    rounded: "{rounded.board}"
    padding: "28px 32px 24px"
  segmented-option-on:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.felt}"
    rounded: "{rounded.board}"
    height: "32px"
  nav-row-active:
    backgroundColor: "{colors.felt-high}"
    textColor: "{colors.ink}"
    rounded: "{rounded.board}"
    padding: "8px 12px"
---

# Design System: PeakCut

## Overview

**Creative North Star: "The Marquee Letterboard"**

PeakCut bills every video on a cinema marquee. The shell is grooved black felt, the video's title is set in push-in letter tiles, and a job's progress runs as a row of marquee bulbs. Everything else is quiet, condensed, letter-white type on felt, ruled with single pixel lines, so the only things that ever glow are the tiles and the bulbs.

It is an operating tool for solo clippers working long sessions, often at night: dark by default (`color-scheme: dark`), dense but legible, with one condensed family doing every job. It explicitly refuses the category default of a near-black SaaS dashboard with purple gradients and soft rounded cards. There are no gradients on surfaces, no glass, no large radii, and no decorative colour.

**Key Characteristics:**
- Grooved felt title board with the title as uppercase letter tiles, once per page.
- Bulb-chase progress as the signature move; nothing else animates continuously.
- Colour carries state, never decoration: amber live, red failed, green posted.
- One condensed type family (Big Shoulders, optical-size axis) ranked by weight and case.
- One UI radius (4px), one-pixel rules, flat tonal layers of felt.

## Colors

A warm near-black felt ground with warm letter-white ink and three single-job signal colours.

### Primary
- **Letter White** (ink): every primary action (filled button), letter tiles, active segmented option, headings and body text, focus outline. It is the "brand colour"; the system has no hue accent for actions.

### Secondary
- **Marquee Bulb Amber** (bulb): live progress only. Lit bulbs in the chase, the running job's percentage and pulsing head bulb in the rail, the "Rendering" state on a clip slot, the working state mark. Two system-level uses sit alongside it: the text caret and the selection highlight. The one brand use is the lit "Cut" tile of the wordmark.
- **Unlit Bulb** (bulb-dim): bulbs not yet reached in the chase.

### Tertiary
- **Stop Red** (fail): failure only. Failed bulbs, failed job labels, struck failed marks, invalid field borders, every error message (which always says what to do next).
- **Posted Green** (posted): posted only. The filled posted state mark. Nowhere else.

### Neutral
- **Felt** (felt): page ground, score plate, unselected option cards.
- **Raised Felt** (felt-raised): title board ground under the grooves, panels (account cards, face cam editor, post dialog), clip frame placeholder, rail row hover.
- **High Felt** (felt-high): selected / active rows and option cards, line-button hover, skeleton bars, code chips.
- **Groove** (groove): the darker stripes of the felt (2px every 9px), field wells, the hard under-edge of a letter tile.
- **Rule** (line): default one-pixel borders and dividers.
- **Strong Rule** (line-strong): button and field outlines, segmented control frame, scrollbar thumb, unposted hollow mark.
- **Soft Ink** (ink-soft): secondary text, ledes, step lists, inactive nav rows.
- **Muted Ink** (ink-mute): labels, metadata, placeholders, waiting states (5.6:1 on felt).

### Named Rules
**The One Job Rule.** Each signal colour means exactly one thing. Amber is live progress, red is failure, green is posted. If a colour would need a second meaning, use ink weight or a mark instead.

**The Nothing Else Glows Rule.** Only lit bulbs carry a glow (`0 0 6px 1px` amber at 45%). No other element gets a coloured shadow, gradient fill or tinted surface.

## Typography

**Display Font:** Big Shoulders (with Arial Narrow, sans-serif), loaded via `next/font` with the `opsz` axis and `font-optical-sizing: auto`
**Body Font:** Big Shoulders, same family
**Label/Mono Font:** none; tabular figures (`tabular-nums`) handle numbers

**Character:** One condensed, poster-like grotesque at every size. The optical-size axis gives the letterboard titles their display cut and keeps 13-17px UI text open and readable.

### Hierarchy
- **Display** (700, clamp(28px, 3.4vw, 46px), line-height 1, uppercase, inside letter tiles): the page title only, one per page. A medium size (clamp(22px, 2.4vw, 30px)) exists for smaller boards.
- **Headline** (700, 24-28px, line-height 1, uppercase, 0.04em): section heads ("3 clips", "Finish setting up", account names, dialog title at 26px).
- **Title** (700, 19px, line-height 1.15, sentence case): clip titles. Option-card titles use 16-18px bold uppercase at 0.06-0.08em.
- **Body** (400, 17px, line-height 1.45): default text; ledes at 18px capped at 60-62ch, error detail capped at 80ch.
- **Body small** (400, 14-15px, snug): metadata, help text, clip reasons (clamped to three lines).
- **Label** (600, 13px, 0.16em, uppercase, muted ink): form legends and list section labels. Field captions run 14px at 0.1em.
- **Button** (700, 15px; 13px small, 0.1em, uppercase).
- **Score** (900, 26px, tabular): the score plate on each clip.

### Named Rules
**The One Family Rule.** Rank by weight and case, never by a second typeface. Uppercase plus tracking marks controls and labels; sentence case marks content people read.

**The Tabular Count Rule.** Percentages, scores, timestamps and character counts use tabular figures so they do not jitter while updating.

## Layout

A fixed left rail (272px) beside a fluid main column at `lg` (1024px) and up; below that the rail collapses into a sticky 64px top bar with the wordmark, an Accounts icon button and a small "New" primary button over a 95% felt backdrop blur.

Main content is centred in a max-width container (1180px home, 1400px job page, 980px settings) with 16px side gutters on phones and 32px from `sm`. Every page opens with the grooved title board (20/32px horizontal padding, 28-36px top). The clip grid is 2 columns on phones, 3 at `md`, 5 at `xl`, with 16px column and 32px row gaps; each clip is a 9:16 frame. Card internals push actions to the bottom (`margin-top: auto`) so marks and buttons line up across a row.

Spacing steps observed: 4, 8, 12, 16, 20, 24, 32, 40, 48px. Sections separate at 32-48px; controls inside a group at 8px.

## Elevation & Depth

Flat tonal layering. Depth comes from stepping felt (groove, felt, raised, high) and one-pixel rules, not shadows. Shadows exist only where the world has physical objects: tiles pressed into felt, the score plate and play button floating over video, and lit bulbs.

### Shadow Vocabulary
- **Tile press** (`box-shadow: 0 2px 0 var(--groove), 0 3px 6px rgb(0 0 0 / 0.35)`): letter tiles, so they sit in the felt grooves.
- **Over-video float** (`box-shadow: 0 2px 8px rgb(0 0 0 / 0.45)`; play button `0 4px 14px rgb(0 0 0 / 0.45)`): readable chips on top of clip thumbnails.
- **Bulb glow** (`box-shadow: 0 0 6px 1px rgb(255 180 61 / 0.45)`): lit bulbs only.
- **Field focus halo** (`box-shadow: 0 0 0 3px rgb(244 239 230 / 0.14)`): focused fields.

### Named Rules
**The Felt Is Flat Rule.** Panels, cards, dialogs and the rail have no shadow. Separate them with a felt step and a one-pixel rule.

## Shapes

One UI radius: gently squared corners (4px) on buttons, fields, cards, the title board, the rail rows, segmented control and dialog. Letter tiles, the score plate, code chips and the face cam box are tighter (2px) because they read as physical plates. Bulbs, state marks and the play button are full circles. Borders are always one pixel (1.5px on 11px state marks). The felt grooves are a repeating horizontal stripe, 2px of groove every 9px, and appear only on title boards.

## Components

### Buttons
Tactile, uppercase, squared.
- **Shape:** gently squared (4px), 40px tall, 16px side padding; small is 32px with 12px padding and 13px text.
- **Primary:** letter-white fill, felt text. Hover lifts to a brighter paper white.
- **Line:** transparent with a strong-rule outline and ink text; hover brightens the outline to soft ink and fills high felt.
- **Active:** presses down 1px. **Disabled:** a waiting primary turns into a ruled outline with muted text (reads "not yet", not broken); other buttons drop to 40% opacity.
- Icon-only buttons are small line buttons with 8-10px padding.

### Chips (state marks)
- **Style:** 11px circles in a fixed cell beside a platform code (YT, IG): hollow strong rule = not posted, amber ring pulsing = uploading, filled green = posted, red ring with a diagonal strike = failed.

### Cards / Containers
- **Corner Style:** 4px.
- **Background:** raised felt for panels; felt or high felt for selectable option cards.
- **Shadow Strategy:** none (see Elevation).
- **Border:** one-pixel rule; selected option cards switch to an ink border on high felt with a check icon.
- **Internal Padding:** 16-24px.

### Inputs / Fields
- **Style:** groove-dark well, one-pixel strong rule, 4px radius, 44px minimum height, 17px text, amber caret. Selects carry a drawn soft-ink chevron.
- **Focus:** border turns ink plus a 3px faint ink halo; no outline.
- **Error / Disabled:** `aria-invalid` turns the border red, with a red message beneath that says how to fix it.

### Navigation
- **Rail:** wordmark, a full-width "New video" line button, a "Jobs" label over job rows, accounts row pinned at the bottom above a rule. Rows are 16px soft-ink text with a right-aligned 13px tabular status (amber live percentage with a pulsing bulb, red FAILED, muted otherwise). Hover fills raised felt; active fills high felt in ink with `aria-current`.
- **Mobile:** sticky top bar (see Layout).
- **Segmented control:** strong-rule frame with 2px inset; options are 32px, 13px bold uppercase; the selected option fills ink with felt text. Two columns on phones.

### Title Board (signature)
Grooved raised felt, 4px radius, one-pixel rule. Holds the page title as letter tiles that push in once per title (staggered 32ms), a soft-ink details line, and on job pages the bulb chase with a tabular uppercase status.

### Bulb Chase (signature)
32 bulbs that shrink to fit the row. Unlit bulbs are dim; lit bulbs are amber with a soft highlight and glow, a brighter pulse travels along them every 1.6s and the head bulb swells. Done turns all bulbs letter white; failed turns the reached bulbs red.

### Score Plate
Felt plate, 2px radius, 26px black-weight tabular score, pinned top-left on the clip frame.

### Motion
Ease-out-expo (`cubic-bezier(0.16, 1, 0.3, 1)`) for all transitions, 120-180ms on controls. Two signature animations: tile push-in (420ms, once per title) and the bulb chase. The post dialog rises 28px over 320ms. Under `prefers-reduced-motion` every animation and transition collapses to near zero and the dialog only fades.

## Do's and Don'ts

### Do:
- **Do** open every page with the grooved title board and set its title as letter tiles, one title per page.
- **Do** use amber only for something live, red only for failure, green only for posted.
- **Do** use the 4px radius on every UI surface and 2px only on physical plates (tiles, score plate).
- **Do** separate surfaces with a felt step and a one-pixel rule.
- **Do** keep component styles in `@layer components` so Tailwind utilities can override width, height and flex.
- **Do** use lucide icons at stroke 1.75 (2 for plus, send, close, retry; 2.25 for checks), 14-16px.
- **Do** write every error as what happened plus what to do next.
- **Do** disable all motion under `prefers-reduced-motion`.

### Don't:
- **Don't** use purple, gradients on surfaces, glassy panels or soft large-radius cards.
- **Don't** add a glow or coloured shadow to anything but a lit bulb.
- **Don't** introduce a second typeface or rank text by a new size when weight and case will do.
- **Don't** put a small uppercase eyebrow label above a heading.
- **Don't** use em-dashes in visible text; use commas, colons or "to".
- **Don't** animate anything continuously other than the bulb chase and the live state pulses.
