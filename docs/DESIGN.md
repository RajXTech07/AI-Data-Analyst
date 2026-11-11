# Design System: AI Data Analyst
**Project ID:** 2853351278076858042

Used by Google Stitch (and any agent connected through the Stitch MCP) as the single source of design rules. Colors are named by purpose, not just appearance.

## 1. Visual Theme & Atmosphere

- **Character:** calm, precise, trustworthy. A professional analytics tool that a first-time student can understand, not a flashy dashboard.
- **Density:** airy at the edges (upload, loading) and moderately dense in data views (issue table, findings). Whitespace separates ideas; borders and light shadows separate cards.
- **Mood words:** clear, evidence-first, quietly confident, friendly.
- **Shape language:** gently rounded corners, thin 1px borders, very soft shadows. No heavy gradients, no glassmorphism, no decorative illustrations.
- **Tone of text:** plain language, short sentences, one-line explanations for any statistical term. Never claim certainty the data does not support ("shows a link, not a cause").
- **Themes:** light theme is default. A dark theme uses the dark tokens below.
- **Platform priority:** desktop-first at 1440px, responsive down to tablet (768px) and phone (390px).

## 2. Color Palette & Roles

### Light theme
| Token | Name | Hex | Role |
|-------|------|-----|------|
| `primary` | Signal Indigo | `#4F46E5` | Main actions (Enter, Analyse, Export), active states, links, focus ring |
| `primary-hover` | Deep Indigo | `#4338CA` | Hover and pressed state of primary |
| `primary-soft` | Indigo Mist | `#EEF2FF` | Selected rows, active filter cards, subtle highlights |
| `accent` | Evidence Teal | `#0D9488` | Evidence and calculation references, "Based on N calculations" links |
| `canvas` | Paper Slate | `#F8FAFC` | Page background |
| `surface` | White | `#FFFFFF` | Cards, panels, table, modals |
| `border` | Hairline | `#E2E8F0` | Card and table borders, dividers |
| `text-strong` | Ink | `#0F172A` | Headings, key numbers |
| `text` | Slate Body | `#334155` | Body text |
| `text-muted` | Quiet Slate | `#64748B` | Helper text, captions, cautions |
| `success` | Clean Green | `#15803D` | Completed steps, "no problems", success toast |
| `success-soft` | Green Mist | `#DCFCE7` | Success chip background |
| `warning` | Caution Amber | `#B45309` | Medium severity, caution notes |
| `warning-soft` | Amber Mist | `#FEF3C7` | Warning chip background |
| `danger` | Alert Red | `#B91C1C` | High severity, errors, destructive actions |
| `danger-soft` | Red Mist | `#FEE2E2` | Error and high-severity chip background |
| `info` | Info Blue | `#1D4ED8` | Low severity and neutral information |
| `info-soft` | Blue Mist | `#DBEAFE` | Info chip background |

### Dark theme
| Token | Hex |
|-------|-----|
| `primary` | `#818CF8` |
| `canvas` | `#0B1120` |
| `surface` | `#111827` |
| `border` | `#1F2937` |
| `text-strong` | `#F8FAFC` |
| `text` | `#CBD5E1` |
| `text-muted` | `#94A3B8` |

### Chart palette (categorical, in order)
`#4F46E5` indigo, `#0D9488` teal, `#D97706` amber, `#DB2777` magenta, `#2563EB` blue, `#65A30D` lime, `#64748B` slate (use for "other").
- Highlight a single series by coloring it `primary` and the rest `#CBD5E1`.
- Never rely on color alone: add direct labels, markers or patterns.
- Sequential scale (heatmaps): light `#EEF2FF` to dark `#3730A3`. Diverging scale (correlation): `#B91C1C` through `#F8FAFC` to `#1D4ED8`.
- Outlier points: `danger` with a ring.

## 3. Typography Rules

- **UI and headings:** Inter, fallback system sans-serif. Friendly, neutral, highly legible.
- **Numbers, statistics, file names, code:** JetBrains Mono, fallback monospace. Used for evidence lines such as "Spearman 0.61, p < 0.001, n = 1,196". Tabular figures wherever numbers are compared.
- **Scale (desktop):**
  - Display (welcome heading): 40px, weight 700, tight tracking (-0.02em), line height 1.15
  - Page title: 28px, weight 650, line height 1.25
  - Section title: 20px, weight 600
  - Card title: 16px, weight 600
  - Body: 15px, weight 400, line height 1.6
  - Small / caption: 13px, weight 400
  - Overline / eyebrow: 12px, weight 600, uppercase, wide tracking (0.08em), `text-muted`
  - Big stat number in summary cards: 32px, weight 700, monospace
- **Rules:** sentence case everywhere, never all caps except the overline. Line length for explanations stays under 70 characters per line. Minimum text size 13px.

## 4. Component Stylings

- **Primary buttons:** solid Signal Indigo, white text, subtly rounded corners (10px), 44px tall, 600 weight. Hover deepens to Deep Indigo. Disabled uses Indigo Mist with muted text. The Analyse and Enter buttons are wide and prominent.
- **Secondary buttons:** white fill, 1px Hairline border, Ink text, same shape. Hover fills with Paper Slate.
- **Text buttons:** Signal Indigo text, no border, underline on hover. Destructive text buttons use Alert Red.
- **Cards and containers:** white surface, 1px Hairline border, 14px rounded corners, soft shadow (`0 1px 2px rgba(15,23,42,0.06)`), 20px to 24px inner padding. Selected or active cards get a 2px Signal Indigo border and Indigo Mist background.
- **Upload drop zone:** large, dashed 2px Hairline border, 16px rounded corners, Paper Slate fill. On drag-over: dashed Signal Indigo border and Indigo Mist fill. Error: dashed Alert Red border with Red Mist fill.
- **Inputs and forms:** white fill, 1px Hairline border, 10px rounded corners, 44px tall, 15px text. Focus shows a 2px Signal Indigo ring with 2px offset. Error shows an Alert Red border and a helper message below.
- **Chat input:** pill-shaped with a magnifier icon at left and a circular send button at right.
- **Chips and badges:** pill-shaped, 24px tall, 12px text, 600 weight. Severity: High on Red Mist with Alert Red text, Medium on Amber Mist with Caution Amber text, Low on Blue Mist with Info Blue text. Confidence chips use the same pattern (High green, Medium amber, Low slate).
- **Summary stat cards:** big monospace number, label above in overline style, one-line hint below in muted text. Clickable, acting as filters.
- **Issue table:** sticky header on Paper Slate, 48px rows, 1px row dividers, checkbox in the first column, hover row in Indigo Mist at 50%. Numeric columns right-aligned in monospace.
- **Finding cards:** title, explanation, monospace evidence line on a Paper Slate rounded strip, chart, muted caution line, then an Evidence Teal link "See how this was calculated".
- **Charts:** white card background, light horizontal gridlines only, no chart borders, 12px axis labels in Quiet Slate, tooltips as small dark cards (Ink fill, white text, 8px radius), chart-type switcher as a small segmented control.
- **Chat bubbles:** user bubbles on Indigo Mist, answer bubbles on white with a Hairline border. Answers end with a small Evidence Teal label such as "Based on 2 calculations".
- **Top bar:** 64px tall, white, bottom Hairline border. Menu icon at far left, wordmark next to it, account button at far right (outlined pill with user icon and "Sign in", or the avatar when signed in).
- **Navigation drawer:** 320px, white, slides over a dimmed overlay (Ink at 40%), 0 rounded corners on the left edge.
- **Modals:** 440px, 16px rounded corners, soft larger shadow, tabbed header, a clear close icon.
- **Progress and loading:** circular spinner with a thin 4px Signal Indigo ring on a Hairline track; step checklist with check (Clean Green), spinner (Signal Indigo) and empty circle (Hairline) states.
- **Toasts and banners:** 12px rounded, left color bar by type, 14px text, auto-dismiss toast after 4 seconds.
- **Icons:** outlined line icons, 20px, 1.75px stroke, Slate Body color, consistent set (Lucide style).

## 5. Layout Principles

- **Grid:** 12 columns, 24px gutters, content max width 1200px, centered. The Results screen uses three columns: 260px action panel, flexible center, 360px chat panel.
- **Spacing:** 8px base unit. Allowed steps: 4, 8, 12, 16, 24, 32, 48, 64. Cards sit 24px apart; sections 48px apart.
- **Hierarchy:** one primary action per screen, placed at the end of the reading path (Enter, Analyse). Secondary actions are visually quieter.
- **Whitespace strategy:** generous on the welcome and loading screens; tighter but never cramped in the issue table and findings.
- **Sticky elements:** top bar on every screen; bottom action bar on the review screen. Nothing else sticks.
- **Scrolling:** on the Results screen only the center column scrolls; side panels stay in place.
- **Responsive:** at tablet width the chat becomes a collapsible panel; at phone width the chat is a bottom sheet and summary cards stack in two columns.

## 6. Content and States

- **Sample data:** always realistic (student_performance.csv, 1,200 rows, 12 columns, attendance, marks, department, assignment_score). No lorem ipsum.
- **Empty state:** short friendly line, one clear next action. Example: "No problems found. Your data looks clean."
- **Error state:** say what happened and that the file is safe, then offer a way forward. Example: "We could not read this file. Check that it has a header row."
- **Loading:** show real steps instead of a bare spinner.
- **Statistical wording:** explain in plain language first, show the numbers second in monospace. Always pair a correlation with the caution "This shows a link, not a cause."
- **Original data safety:** wherever fixes are shown, state that the original file stays unchanged.

## 7. Accessibility

- Text and interactive elements meet WCAG AA contrast (4.5:1 for body text, 3:1 for large text and UI borders).
- Visible focus ring on every interactive element; full keyboard navigation for the drawer, modal, table checkboxes and chat.
- Minimum touch target 44x44px.
- Severity and confidence are always shown with text, not color alone.
- Charts include a text summary and a "View as table" option.
- Respect reduced-motion settings: replace spinner animation with a static progress indicator.

## 8. Do's and Don'ts

**Do**
- Keep one primary action per screen.
- Show evidence next to every claim.
- Use Evidence Teal only for calculation references.
- Keep chart colors consistent across screens.
- Write in plain sentence case.

**Don't**
- Don't use gradients, glassmorphism, neon colors or stock photos.
- Don't use red or green alone to signal meaning.
- Don't put more than 7 colors in one chart.
- Don't hide the "original file unchanged" message.
- Don't use jargon without a one-line explanation.
- Don't use more than two font families.
