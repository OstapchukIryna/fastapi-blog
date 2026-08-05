---
name: Called Mad
description: A backend engineer's blog and work sample — amber on ink, editorial serif inside a code-editor palette.
colors:
  filament-amber: "#ffb703"
  filament-amber-hot: "#fb8500"
  amber-hairline: "rgba(255, 183, 3, 0.4)"
  ink: "#1e1f1c"
  deep-ink: "#14150f"
  raised-ink: "#272822"
  paper: "#f8f8f2"
  bright-paper: "#ffffff"
  muted-sand: "#a39e8b"
  hairline: "#3e3d32"
  signal-rose: "#ff6188"
  signal-rose-deep: "#c9134e"
typography:
  display:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "clamp(2.75rem, 9vw, 4.25rem)"
    fontWeight: 700
    lineHeight: 0.92
    letterSpacing: "-0.045em"
  voice:
    fontFamily: "Newsreader, Georgia, serif"
    fontSize: "clamp(2rem, 5.6vw, 3.15rem)"
    fontWeight: 400
    lineHeight: 1.14
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "clamp(2rem, 6vw, 3rem)"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.04em"
  title:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "clamp(1.6rem, 4.5vw, 2.15rem)"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.025em"
  body:
    fontFamily: "Newsreader, Georgia, serif"
    fontSize: "1.0625rem"
    fontWeight: 400
    lineHeight: 1.7
  label:
    fontFamily: "JetBrains Mono, ui-monospace, monospace"
    fontSize: "0.72rem"
    fontWeight: 400
    letterSpacing: "0.09em"
  code:
    fontFamily: "JetBrains Mono, ui-monospace, monospace"
    fontSize: "0.9rem"
    lineHeight: 1.6
rounded:
  md: "0.5rem"
  full: "50%"
spacing:
  inset-card: "2rem"
  inset-panel: "1.5rem"
  gap-inline: "1.5rem"
  gap-tight: "0.6rem"
components:
  button-primary:
    backgroundColor: "{colors.filament-amber}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    padding: "0.6rem 1.25rem"
  button-primary-hover:
    backgroundColor: "{colors.filament-amber-hot}"
    textColor: "{colors.ink}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.muted-sand}"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    padding: "0.5rem 1.15rem"
  button-ghost-active:
    backgroundColor: "transparent"
    textColor: "{colors.filament-amber}"
  button-danger:
    backgroundColor: "{colors.signal-rose}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
  input-text:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    rounded: "{rounded.md}"
  chip-tag:
    backgroundColor: "transparent"
    textColor: "{colors.muted-sand}"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    padding: "0.35rem 0.7rem"
  card-surface:
    backgroundColor: "{colors.raised-ink}"
    textColor: "{colors.paper}"
    rounded: "{rounded.md}"
    padding: "{spacing.inset-card}"
  panel-now:
    backgroundColor: "{colors.raised-ink}"
    textColor: "{colors.paper}"
    rounded: "{rounded.md}"
    padding: "1.5rem 1.75rem"
  avatar:
    rounded: "{rounded.full}"
    size: "72px"
---

# Design System: Called Mad

## Overview

**Creative North Star: "The Lit Terminal"**

Monokai is a code editor theme, and this site wears it on purpose. The ground is
the editor's background, the text is its foreground, and the one accent is the
warm highlight a syntax theme reserves for the thing that matters. But an editor
is built for scanning code in short bursts, and this surface has to hold long
prose. So the palette stays and the typography changes: an editorial serif is
laid into the editor's dark, given a 68-character measure and a 1.7 line height,
until the environment a backend engineer actually lives in becomes somewhere you
can read a two-thousand-word post-mortem without leaving.

Everything is flat. There is not a single `box-shadow` in the system — depth
comes from a hairline border and a change of ground, never from a simulated
light source. Elements are quiet at rest and answer only when touched, in 200ms,
on colour or border. Nothing animates on its own, nothing floats, nothing
pulses for attention.

The restraint is the argument. This site is a work sample for a backend
engineer, so a decorative flourish that cannot be justified costs more than it
adds. One accent, two themes, three typefaces, no shadows, and every contrast
ratio written into the stylesheet next to the value it justifies.

**Key Characteristics:**
- One accent colour, used as a signal rather than as decoration
- Zero shadows; depth is border and ground only
- Editorial serif for prose and for the author's voice, a grotesque for names, monospace for every service string
- Dark is the canonical theme; light is a fully maintained alternative
- Motion is confirmation, never entertainment

## Colors

A code editor's palette carried into long-form reading: one warm signal on a
near-black ground, with every value that failed a contrast check corrected and
the ratio recorded beside it.

### Primary
- **Filament Amber** (`#ffb703`): the only accent in the system. It marks state
  and path, never surface — the pinned label, the `Now` panel's left rule, links,
  list markers, the reading indicator, focus rings, and the primary button's
  fill. On ink it measures 9.49:1.
- **Filament Amber Hot** (`#fb8500`): reserved for the hover state of a solid
  amber fill, so the button darkens rather than glows.
- **Amber Hairline** (`rgba(255, 183, 3, 0.4)`): a 40% amber used only for
  borders that warm on hover or focus, never for text.

### Neutral
- **Ink** (`#1e1f1c`): Monokai's background; the page ground in the dark theme
  and the text colour printed on amber fills.
- **Raised Ink** (`#272822`): Monokai's surface, used as the single elevation
  step. Cards and panels sit on this and nothing else.
- **Deep Ink** (`#14150f`): below the ground, used only for modal surfaces so a
  dialog reads as a layer over the page rather than a continuation of it.
- **Paper** (`#f8f8f2`): Monokai's foreground; body text on dark, and the page
  ground in the light theme where the same two values simply trade places.
- **Bright Paper** (`#ffffff`): headings and emphasised text on dark only.
- **Muted Sand** (`#a39e8b`): secondary text — metadata, hints, captions,
  inactive labels. Monokai's native comment `#75715e` measures 3.38:1 here and
  was lightened to 6.17:1. That ratio is against `Ink`; on `Raised Ink`, where
  it actually appears inside cards and the `Now` panel, it measures 5.54:1.
- **Hairline** (`#3e3d32`): every border and divider in the system.

### Tertiary
- **Signal Rose** (`#ff6188`): destructive actions only — the delete button, an
  invalid field, a validation summary. Monokai's pink `#f92672` measures 4.38:1
  on ink and was lightened to 5.77:1.
- **Signal Rose Deep** (`#c9134e`): the pressed and hover fill under Signal Rose.

### Named Rules

**The Single Filament Rule.** There is one accent. If a design needs a second
hue to separate two things, the hierarchy is wrong — fix it with weight,
position, or ground instead. The only sanctioned exception is Signal Rose, and
only for destruction and error.

**The Token-Only Rule.** Colour exists exclusively as a custom property in
`:root` and the `[data-bs-theme]` blocks. A hex literal inside a component or a
template is a defect, because it is the one thing that cannot follow a theme
switch.

**The Measured Contrast Rule.** Monokai heritage never outranks legibility. When
a native value fails, it is adjusted and the resulting ratio is written into the
stylesheet as a comment next to it. A colour without a recorded ratio has not
been checked.

## Typography

**Display Font:** Archivo (with system-ui, sans-serif)
**Body Font:** Newsreader (with Georgia, serif)
**Label/Mono Font:** JetBrains Mono (with ui-monospace, monospace)

**Character:** A grotesque names things, a literary serif says them, and a
monospace handles everything the machine knows. The three-way split does the
hierarchy work, which is why body copy never needs a third weight or a fourth
size to be readable.

Archivo replaced Space Grotesk as the display face on 29 Jul 2026. Space
Grotesk had become one of the handful of faces every generated interface
reaches for, and a work sample whose argument is deliberate choice cannot be
set in the default of the moment. Archivo keeps the job description — a
grotesque, engineered rather than styled — and holds the hero's -0.045em
tracking better, being the narrower and sturdier of the two. Nothing else in
the system moved: the serif and the monospace were never the problem.

### The scale

Every size is a token in `:root`. Seven text steps and four display steps, and
nothing outside them. The single exception is documented under Code below.

| Token | Value | Used for |
|---|---|---|
| `--text-label` | 0.72rem | service strings, always monospace uppercase |
| `--text-xs` | 0.8rem | brand mark, compact buttons |
| `--text-sm` | 0.9rem | code blocks, monospace data, tables |
| `--text-base` | 1.0625rem | body copy, card headings, form text |
| `--text-md` | 1.2rem | post prose, pull quotes, lead paragraphs, `h3` |
| `--text-lg` | 1.4rem | archive titles, dialog titles |
| `--text-xl` | 1.7rem | `h2` inside a post |
| `--display-card` | `clamp(1.6rem, 4.5vw, 2.15rem)` | the lead post's heading |
| `--display-page` | `clamp(2rem, 6vw, 3rem)` | any page's own `h1` |
| `--display-voice` | `clamp(2rem, 5.6vw, 3.15rem)` | the author speaking, serif |
| `--display-hero` | `clamp(2.75rem, 9vw, 4.25rem)` | front-page masthead |

### Hierarchy
- **Display** (Archivo 700, `--display-hero`, line-height 0.92, tracking
  -0.045em): page mastheads. One per page, and only where the page names itself.
- **Voice** (Newsreader 400, `--display-voice`, line-height 1.14, tracking
  -0.02em): the author speaking in first person at display size. Real italics
  carry the emphasis inside it, so no colour is spent on the accent word.
- **Headline** (Archivo 700, `--display-page`, tracking -0.04em): a page's
  own title — post, error, form, author. One definition, four surfaces; they
  used to be four near-identical clamps.
- **Title** (Archivo 700, `--display-card`): the lead post's heading;
  `--text-lg` for archive rows.
- **Body** (Newsreader 400, `--text-base`; `--text-md` for post prose,
  line-height 1.7): all reading text. Post bodies are capped at 68ch, which
  decides readability more than any other single value.
- **Label** (JetBrains Mono 400, `--text-label`, uppercase, tracking 0.09em):
  dates, counts, tags, navigation, eyebrows, field labels, table headers,
  buttons.
- **Code** (JetBrains Mono, `--text-sm` in a block): inline code is the one
  size not on the ramp — it is set at `0.88em`, a relative optical correction
  because a monospace face carries a larger x-height than the serif around it.
  Inside a block the correction is switched off, or it would apply twice.

### Named Rules

**The One Ramp Rule.** A literal `font-size` in a component is a defect. If a
step is missing, add it to the ramp and to this table; do not solve it locally.

**The Voice-Is-Serif Rule.** Wherever the page speaks in the first person at
large size, it speaks in Newsreader, not Archivo. The grotesque names
things; the serif says them. This is why the front page's thesis reads as a
person talking rather than a brand announcing, and it is a system rule, not a
one-off for the hero.

**The Mono-Label Rule.** Every service string is `.mono-label`: monospace,
0.72rem, uppercase, 0.09em tracking. Metadata is not body text set smaller, and
it never competes with prose for the same visual channel.

## Layout

A single centred column of 760px (`--measure`), with 1.25rem inline padding, and
no sidebar anywhere — an earlier sidebar was removed because it spent a third of
the width on placeholders. Prose narrows further to 68ch inside that column, so
the measure serves reading rather than filling the viewport.

Vertical rhythm is carried by hairline rules rather than by boxes: sections are
separated by a 1px `Hairline` border and generous space above it, and list rows
(archive items, topic rows) are divided by `border-top` alone with no card
around them. Cards appear only where something is genuinely a distinct object —
the lead post, related posts, the `Now` panel, the contact block.

Fixed navigation sits at the top at 3.75rem, with a blurred translucent ground
(`backdrop-filter: blur(10px)`) so content passing beneath stays legible.

### Two measures

The column has a measure. The chrome — the navbar and the footer — does not: it
is inset from the window by the same 1.25rem the column uses, with no ceiling.
Below 760px the two coincide exactly, so the brand sits directly above the text
and the footer's label below it, and no second breakpoint is needed. Above it,
the chrome tracks the window while the column stays 760px.

**The Competing-Box Rule.** The chrome may be wider than the measure, but it may
never be a *centred box* of its own. That, not the size of the gap, is what
reads as a craft error: two centred containers of nearly the same width look
like a failed attempt to match. Bootstrap's 1140px container was exactly that,
and it is why the chrome was pinned to the measure for a while — which fixed the
misalignment and cost the page its desktop, since a full-bleed bar with its
contents pinched into the middle 760px is what makes a deliberately narrow
column read as a phone layout stretched onto a desktop.

The gap itself is not the thing to police. It is `(viewport - 760) / 2`, so it
passes through any interval you try to forbid — at 1280px it lands on 260px,
inside the range the old comment called the error. Measured at 1280 with the
chrome flush to the glass, nothing reads as misaligned, because there is no box
to fail to match. A ceiling is what to avoid: with one, a wide enough window
turns the chrome back into a centred box, and at 2560px its contents float
nearly 500px inside a full-bleed bar — the original disease, milder.

Grounds and their edges bleed to the window: the navbar's translucent ground,
the hairline that ends it, and the footer's rule, which spans the chrome it
belongs to. Rules *inside* the column stay on the measure.

Responsive behaviour has one breakpoint at 575.98px. Below it: horizontal pairs
become vertical stacks (author masthead, author byline, about intro, spec and
`Now` rows), full-width buttons become the primary touch target, and card insets
drop from 2rem to roughly 1.35rem. Type needs no breakpoint because every
heading is a `clamp()`.

### Named Rules

**The 760 Rule.** The column is 760px and prose is 68ch. Widening either to fill
a large screen is a regression, not a fix. It governs the column and the prose
inside it, and nothing else — the navbar and the footer are not the column, and
they follow the Competing-Box Rule above instead.

**The Hairline-Over-Box Rule.** A list is divided by a rule, not wrapped in
cards. Reach for a card only when the thing inside it is a discrete object that
can be acted on.

## Elevation & Depth

This system has no shadow vocabulary at all. There is not one `box-shadow` in
it, and the only two occurrences of that property in the stylesheet set it to
`none` to remove Bootstrap's focus glow.

Depth is expressed by exactly two means: a 1px `Hairline` border, and a change
of ground from `Ink` to `Raised Ink`. There is a single elevation step — page
ground, then raised surface — with one exception above the page rather than on
it: modals sit on `Deep Ink`, darker than the page, so a dialog reads as a
separate layer instead of a continuation of the surface underneath.

### Named Rules

**The No-Shadow Rule.** Surfaces are flat, always. If something needs to feel
raised, change its ground and give it a hairline. A drop shadow anywhere in this
system is a defect.

**The One-Step Rule.** There is one elevation step, not a ramp. A card inside a
card is a sign the composition is wrong.

## Shapes

Corners are gently rounded at a single 0.5rem radius applied through
`--bs-border-radius`, so buttons, cards, panels, inputs, tags and modals all
share one silhouette. Avatars are the only exception, fully circular at 50%, and
are forced to greyscale so a photograph can never introduce a second colour into
a one-accent system.

Every border in the system is 1px `Hairline`, on every side, with one exception:
a pull quote carries a 2px `Filament Amber` rule on its leading edge. That is a
typographic device for a quotation, not a card decoration, and it is the only
place a thick coloured edge appears.

Cards do not get one. A 2px accent border down one side of a card is the single
most recognisable tell of a generated interface, and it was also redundant here:
every card that carried one already named its own state in words — `Pinned`,
`Now`, `Get in touch`, `Not saved` — in the accent colour, one line above.

### Named Rules

**The Named-State Rule.** When a block is the current, leading or failing one,
say so in a word set in the accent, and let the raised ground and the hairline
do the rest. Do not mark it with a coloured edge, a glow, or a tinted fill.

**The One Border Rule.** 1px `Hairline`, all four sides. The pull quote is the
only exception in the system, and adding a second one needs a reason written
down here.

## Components

### Buttons
- **Shape:** the shared gently-rounded corner (0.5rem), never pill, never square.
- **Primary:** solid fill with inverted text, 0.6rem/1.25rem padding and a 44px
  minimum height, set in the label typeface — monospace, uppercase, 0.09em
  tracking, so even the main call to action speaks in the interface's service
  voice rather than shouting in the display face. The fill follows the theme's
  own accent through `--cta-bg`: `Filament Amber` on dark, the burnt link colour
  on light. Amber on paper measures 1.64:1, under the 3:1 floor for a non-text
  element, and would put two accent hues on screen at once.
- **Hover / Focus:** the fill darkens to `Filament Amber Hot` over 200ms. Focus
  shows a 2px amber outline offset by 3px. Disabled keeps the amber and drops to
  45% opacity rather than falling back to a grey Bootstrap never themed.
- **Ghost:** transparent fill, 1px `Hairline` border, `Muted Sand` label; the
  border and text warm toward the foreground on hover. Used for record actions
  such as pin and delete.
- **Ghost, active state:** when the state it toggles is on, the label and border
  take `Filament Amber` and `Amber Hairline` — the button shows a state, not
  just an action.
- **Destructive:** `Signal Rose` fill with `Ink` text, deepening to `Signal Rose
  Deep`, where the label lightens to `Paper` for contrast on the darker fill.

### Chips (tags)
- **Style:** transparent with a 1px `Hairline` border and `Muted Sand` label at
  0.35rem/0.7rem, in the label typeface, prefixed with `#`.
- **State:** on hover the label takes `Filament Amber` and the border takes
  `Amber Hairline`. There is no selected variant; tags are navigation.

### Cards / Containers
- **Corner Style:** 0.5rem, shared with everything else.
- **Background:** `Raised Ink` — the single elevation step.
- **Shadow Strategy:** none. See Elevation & Depth.
- **Border:** 1px `Hairline`, warming to `Amber Hairline` on hover or
  focus-within.
- **Internal Padding:** 2rem for a lead or contact card, 1.5rem for a related
  card, dropping to about 1.35rem below 576px.

### Inputs / Fields
- **Style:** the field is *darker* than the surface it sits on — `Ink` on
  `Raised Ink` — with a 1px `Hairline` border and the shared 0.5rem radius, so a
  writable area reads as recessed rather than raised.
- **Focus:** the border warms to `Amber Hairline` and Bootstrap's glow is
  removed entirely; the outline ring does the work instead.
- **Error:** border takes `Signal Rose`, Bootstrap's inline icon is suppressed
  because it shifts the text and duplicates the message, and the message sits
  directly beneath the field, above the hint.
- **Content field:** the markdown body input is monospace at 0.9rem with
  vertical-only resize and a 20rem floor — it is code, and it is set as code.

### Navigation
- **Style:** fixed top bar on a translucent ground with a 10px backdrop blur and
  a hairline bottom border. Links are label typography; the active section takes
  `Filament Amber`.
- **Author action:** the single author-only entry point is outlined rather than
  filled, so it reads as available without competing with the site's own
  sections.
- **Mobile:** collapses to a borderless toggler below 768px.

### Dialogs and result windows
- **Ground:** `Deep Ink`, a hairline border, the shared 0.5rem radius. Every
  dialog carries `data-bs-theme="dark"` for the same reason the navbar does:
  the surface is dark in both themes, so the text inside must take the dark
  theme's tokens rather than the page's. Without it the light theme printed a
  near-black heading on a near-black ground.
- **Two windows, not many.** `#successModal` and `#errorModal` live in the
  layout and serve every form on the site, so "saved" looks the same on a post
  as in the profile. Their heading, message and button label are written per
  call — a deletion is not "Saved", and a button that navigates does not say
  "Close".
- **Heading:** display face at `--text-lg`, coloured by outcome — `Filament
  Amber` for success, `Signal Rose` for failure. Colour rather than an icon,
  because an icon would have to be duplicated in text for a screen reader.
- **Buttons:** the same two the rest of the system uses — primary fill for the
  action, ghost for dismissal — in label typography at the 44px floor. A
  dialog is the one screen a person is made to look at, and it is the last
  place to leave a Bootstrap default.
- **Failure:** `role="alertdialog"` with the message wired through
  `aria-describedby`, so it is read out and not just named. Refused fields
  carry `aria-invalid` alongside the rose border, because the border is colour
  and colour alone says nothing.
- **Never two at once.** A confirmation hands over to a result window only
  after `hidden.bs.modal`. Bootstrap counts one backdrop and one scroll lock
  per open dialog, and overlapping them leaves the page scroll-locked with no
  way out but a reload.

### Account pages
- **Shape:** a single 26rem column, centred, with the form on `Raised Ink`
  inside it. Narrower than the 760px measure on purpose — sign-in and
  registration are four fields and a decision, and a full-width form would
  make them look like work.
- **Density:** fields sit 1.25rem apart rather than the editor's 1.75rem.
  Four of them in a 26rem card at the editor's spacing did not fit a phone
  screen in one look.
- **Primary action:** full width, because on a phone it is the only thing on
  the page worth touching.
- **The reason line:** somebody sent here from a page they could not open is
  told so above the form, in the `.form-summary` block. Being bounced without
  explanation reads as having clicked the wrong thing.

### Sectioned settings
The profile is five sections divided by hairlines, each saving itself. One
button at the foot saving everything at once would mean a person changing a
password also re-submits their name, and an error in either would be reported
about both.

- **Heading:** display face at `--text-lg`, with an optional line of
  explanation under it in `Muted Sand`.
- **Own control:** each section ends in its own button, labelled with what that
  section does — `Save`, `Change password` — never a generic `Save changes`.
- **Danger zone:** named in `Signal Rose` and otherwise identical to every
  other section. See the Named Rule below.
- **The photo control:** the native file input cannot be styled, so it is
  visually hidden and its `<label>` is the button; the focus ring moves onto
  the label so keyboard reach stays visible. Choosing a file *is* the upload —
  a second confirming click would decide nothing. The button says `Choose a
  photo` or `Replace` depending on what is there, and `Remove` appears only
  when there is something to remove.

Uploads are fitted to 300×300 and stored as JPEG, so every avatar in the
system is the same shape and weight. The stand-in for an account with no
photo of its own is `static/profile_pics/default.jpg`, cut to the same size by
the same pipeline — uploads live under `media/` and are not part of the
source, the default is an asset of the interface and is.

### Named Rules

**The Named-Danger Rule.** A destructive area is announced by its heading in
`Signal Rose`, and by nothing else: same ground, same hairline, same spacing
as its neighbours. A tinted panel behind a red border is the most recognisable
tell of a generated interface, and it says less than the word does — the row
already carries a sentence explaining what will be lost.

### The Now Panel (signature)
A status card carrying what the author is building, what is next, and a link to
the source, with the primary contact action attached to its foot. `Raised Ink`
ground, 1px hairline, 2px amber left rule, label-typeset keys in a two-column
grid that stacks below 576px, and a hand-maintained date in its header. It is
the one component that states present-tense truth, which is why the date is
edited by hand and never generated.

### The Title Wipe (signature)
Post titles carry an amber underline drawn with a `linear-gradient` background
sized `0% 2px` and grown to `100% 2px` over 280ms when the card is hovered or
focused within. It is the only motion in the system that draws rather than
fades, and it is why `text-decoration` is suppressed on those links — otherwise
a second line renders over the first.

### The Reading Indicator (signature)
A 2px `Filament Amber` bar fixed at the top of a post, scaled on the X axis from
a true `scrollY` ratio, with no starting offset. It exists only on the post page.

## Do's and Don'ts

### Do:
- **Do** put every colour in `:root` / `[data-bs-theme]` and reference the token.
- **Do** record the contrast ratio in a comment whenever a colour is chosen or
  adjusted, the way `#a39e8b` (6.17) and `#ff6188` (5.77) already are.
- **Do** name a block's state in a word set in the accent, and let the raised
  ground and the hairline carry the rest.
- **Do** take every size from the type ramp; a literal `font-size` is a defect.
- **Do** set every service string — dates, counts, tags, nav, buttons, field
  labels — in `.mono-label`.
- **Do** use Newsreader whenever the page speaks in first person at large size.
- **Do** keep prose at 68ch and the column at 760px.
- **Do** express depth with a hairline and a change of ground.
- **Do** keep transitions at 200ms on colour, border-colour or transform, and
  keep the `prefers-reduced-motion` block honoured.
- **Do** verify both themes; light is a maintained alternative, not a fallback.

### Don't:
- **Don't** add a `box-shadow`. There are none, and that is the system.
- **Don't** put a thick coloured border down one side of a card. It is the most
  recognisable tell of a generated interface, and the accent label already says
  what the edge would.
- **Don't** introduce a second accent hue. Signal Rose is for destruction and
  error only.
- **Don't** hardcode a hex value in a component or a template.
- **Don't** nest a card inside a card; there is one elevation step.
- **Don't** animate anything on its own — no autoplay, no pulse, no bounce, no
  slide. Motion answers an action.
- **Don't** show progress, freshness or state the system has not actually
  measured. The reading bar starts at zero and the `Now` date is hand-set on
  purpose.
- **Don't** reach for developer-portfolio clichés: terminal window mockups,
  typing animations, matrix rain, a `hello world` hero. The palette already
  says where this author works; acting it out is costume.
- **Don't** drift toward a generic SaaS landing page — gradient hero, pastel
  illustrations, large rounded cards floating on shadows.
- **Don't** leave anything looking like untouched Bootstrap: default blue
  buttons, default shadows, default radii. Dialog footers and file controls
  are the two places this keeps coming back.
- **Don't** wrap a danger zone in a red panel. Name it in `Signal Rose` and
  leave the ground alone.
- **Don't** put two hairlines within a couple of centimetres of each other. A
  section already separated by a rule does not need a second one inside it;
  read together they look like a stripe rather than a boundary.
