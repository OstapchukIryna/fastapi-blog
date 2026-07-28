---
target: the home page
total_score: 23
max_score: 36
na_heuristics: 10
p0_count: 2
p1_count: 3
timestamp: 2026-07-28T16-09-28Z
slug: templates-home-html
---
Method: dual-agent (A: a13d20070ba80968f · B: a49e0c47ccc331a12)

Surface: home page (`templates/home.html`), mode **Persuade**. Inspected 1280×900, 1280×2200, 1920×1000, 375×812, dark and light.

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Active nav, theme label, `Updated`, `Pinned`, reading times all present; but 5 links open new tabs with no affordance, and no visited state on post titles. |
| 2 | Match System / Real World | 3 | `Building / Next / Source`, `Write to me`, `3 min` are exemplary; `DARK ▾` is a bare state word, and "Topics" vs `#python` names one concept twice. |
| 3 | User Control and Freedom | 3 | Three-mode theme switch with persistence; but no skip link (11 tab stops to first content link) and 5 unannounced new-tab exits. |
| 4 | Consistency and Standards | 2 | Navbar/footer sit on Bootstrap's 1140px container while content is 760px — brand floats 190px (@1280) to 290px (@1920) left of everything. Amber left rule marks two adjacent blocks. Light theme runs two accent hues at once. |
| 5 | Error Prevention | 2 | The `_contact.html` macro makes dead `#` links structurally impossible. Against that: 20px tap targets over a full-card click overlay, a 39px primary CTA, and `Sign in` leading to a form labelled "Not wired up yet." |
| 6 | Recognition Rather Than Recall | 3 | Full-sentence titles, summaries, tags, dates, section names — nothing hidden. No visited state; theme control's meaning must be recalled. |
| 7 | Flexibility and Efficiency | 2 | Theme persistence and whole-card hit areas are real accelerators. Missing the recruiter's fastest path: no copyable email string, no CV, no RSS. |
| 8 | Aesthetic and Minimalist Design | 3 | Craft floor is genuinely excellent — zero shadows, one accent, 760px measure, disciplined three-typeface hierarchy. But the hierarchy is inverted: the largest element is a writing-habit sentence and the role line is the smallest type on the page. |
| 9 | Error Recovery | 2 | Thin surface. The honest empty state is right; the CTA's fallback string ("Add telegram or email to SITE in templating.py") is developer-facing copy that would ship to visitors. |
| 10 | Help and Documentation | n/a | A five-post personal home page has nothing to document; `About` covers the only question a visitor has. |
| **Total** | | **23/36** | **Acceptable (64%)** |

## Design Specificity Verdict

**Partially specific — an authored voice on a category-standard skeleton.**

**LLM assessment.** Genuinely authored: the `SOURCE` row inside the Now panel converts PRODUCT's central positioning claim ("the deliverable and the demonstration are the same repository") from an assertion into a structural fact of the interface, and it sits in the same object as the CTA. The typographic split — Newsreader italic at 3.15rem carrying "*didn't work*", Space Grotesk naming things, JetBrains Mono for service strings on a Monokai ground — is a real non-default decision; the category default is a mono or geometric-sans hero. The copy register matches the brand commitment exactly.

Category-interchangeable: the composition is the standard developer-blog template — centred single column, avatar + name, big statement, status card, one hero card, reverse-chronological rows of date / title / two-line excerpt / tags. There is no second reading axis anywhere on the page. The evidence layer does nothing this product needs: these are post-mortems of the author's own mistakes, and nothing in the row structure, ordering or annotation derives from that. And nothing on this page is produced by the backend it advertises — every pixel could be a static file, on a surface whose stated principle is "make invisible backend work visible."

Swap the photograph, the handle and the five titles for a designer's or a founder's and this page serves them without a structural edit.

**Deterministic scan.** `detect.mjs` over the three home-page markup files: **1 finding**, exit 2 — `overused-font` (warning) at `templates/layout.html:31`, flagging Space Grotesk. The same scan over all 10 files in `templates/` returns the identical single finding, so nothing else in the template set trips a rule.

The in-page detector found **8**: `tight-leading` ×1 on `p.hero-statement` (1.14 line-height against a ≥1.3 rule), `side-tab` ×2 on `section.now-panel` and `article.lead-post.is-pinned` (2px left border + 8px radius), `low-contrast` ×5 on `a.post-title`.

Where the two methods agree: the detector's `side-tab` ×2 lands on exactly the two elements the design review independently flagged as the page's "single focus" failure — the Now panel and the pinned lead are both raised cards with the same 2px amber left rule, so the page marks "the leading thing" twice in a row. Two independent methods, same two DOM nodes.

**False positives.** All five `low-contrast` hits are wrong. The detector read `#ffb703` as the text backdrop, but that value is the animated hover underline (`background-size: 0% 2px` at rest, growing to `100% 2px` on hover) and never sits behind the glyphs. The real backdrop is `#272822` or `#1e1f1c`; white on those is roughly 15:1, not the reported 1.7:1. The detector resolved the `background-image` declaration instead of walking to the first opaque painted ancestor.

`tight-leading` is measured correctly but its ≥1.3 threshold is body-copy calibrated and does not scale with font size; it will fire on any display heading with normal display leading. `overused-font` is noted and overridden: DESIGN.md pins Space Grotesk, and a pinned typeface outranks a saturation warning.

Nothing in either scan touched box-shadows or hardcoded colours — the zero-shadow and token-only conventions held.

**Visual overlays.** Injection succeeded and a user-visible overlay rendered in a throwaway tab (8 highlight boxes with labels — "tight line height" on the hero statement, "side-tab accent border" on the Now panel). The overlay helper on port 8400 was stopped and the port confirmed closed.

## Overall Impression

The craft floor here is high and unusual — zero shadows, one accent, measured contrast ratios recorded next to the values that justify them. That is not what this page's problem is. The problem is **priority**: on a surface whose declared job is to make a hiring evaluator want an interview within a minute, the first screen contains no work. The largest, brightest element is a sentence about a writing habit; the one fact a recruiter is scanning for — role and stack — is the smallest type on the page; and the five post-mortems that constitute the entire argument sit 100% below the fold on every viewport tested.

The single biggest opportunity: get evidence into the first screen and let the page end on an invitation rather than a copyright line.

## What's Working

1. **The `SOURCE` row inside the Now panel.** It turns the positioning claim into a verifiable fact placed in the same card as the action, so an evaluator can check the claim and act on it without leaving the object. Most portfolios bury the repo in a footer icon row where it reads as social decoration.
2. **Italic serif carrying the hero emphasis instead of colour.** Setting "*didn't work*" in real Newsreader italic keeps the entire accent budget intact for state — Pinned, Now, links, focus rings, the CTA. This restraint is precisely why the single amber button reads as *the* action.
3. **`_contact.html` refusing to render an unconfigured channel.** It makes the most common portfolio failure — a social link pointing at `#` — structurally impossible, and degrades to an instruction rather than a placeholder.

## Priority Issues

**[P0] The first screen contains no work.**
At 1280×900 the pinned post title starts at y=878 and is cut by the fold; at 375×812 the first title sits at y=989, 177px below it. The entire first screen on laptop and phone is avatar, handle, a writing-habit sentence, a roadmap panel and contact buttons.
*Why it matters:* PRODUCT defines success as leading to interviews and says the visitor evaluates in a minute or two. The evidence that produces interviews is entirely below the fold, while the most valuable real estate goes to self-description.
*Fix:* Collapse the identity block to one line and either move the pinned post above the Now panel or reduce the panel to a single line (`Building X · Next Y · Source →`). Target: pinned title plus one archive title visible at 1280×900, pinned title visible at 375×812.
*Suggested command:* `/impeccable layout`

**[P0] The hero inverts the audience's priority, and the page has no `h1`.**
`document.querySelectorAll('h1').length === 0` — the first heading in the DOM is the lead post's `h2`. `IRYNA · BACKEND PYTHON` renders at 11.52px muted mono, the smallest type on the page, while the writing-habit sentence is 3.15rem.
*Why it matters:* Six seconds of scanning yields a personality statement and no role, no stack. A screen reader and a crawler get no page-level heading. On a site arguing "the implementation is the argument," a missing document heading is a direct hit on that argument.
*Fix:* Make the hero statement (or a role line above it) the `h1`. Promote role and stack out of `.mono-label` into body serif at emphasis colour so both the fact and the voice land.
*Suggested command:* `/impeccable typeset`

**[P1] The page has no ending.**
It terminates on `© 2026 CALLED_MAD` and three 11.5px grey channel words. `.contact-block` — raised ground, 2rem inset, amber left rule, lead line — already exists in `main.css` and is used on About and post pages, but not on home.
*Why it matters:* Peak-end. The evaluator finishes the archive with conviction at its highest and is handed a copyright line. The home page is the one a recruiter actually lands on, and it has the weakest exit on the site.
*Fix:* Append the existing `.contact-block` after the archive with one line of lead copy. No new component, no new copy register.
*Suggested command:* `/impeccable layout`

**[P1] Email is buried behind Telegram, and two adjacent controls share one destination.**
`write_button()` resolves `site.telegram or mailto:site.email`, so the amber CTA is `https://t.me/parzifay` — and the `Telegram` channel link immediately to its right is the same URL. Email is a 40×20px grey word.
*Why it matters:* All three named audiences run on email; Telegram is the author's preference, not theirs. The page's only high-contrast decision point spends half its options on a duplicate.
*Fix:* Make the primary CTA `Email me` (`mailto:` with a prefilled subject), demote Telegram to the channel row, remove the duplicate beside the button. If Telegram stays primary, label the destination and give Email equal weight.
*Suggested command:* `/impeccable clarify`

**[P1] Mobile tap targets are 20px; the primary CTA is 39px.**
Measured at 375×812: `.card-tags a` = 20px tall (`#sql` is 28×20), `.channels a` = 20px, `.now-source` = 20px, `.write-btn` = 39.19px — all under the 44px minimum, and `.stretched::after` covers the whole archive row beneath them.
*Why it matters:* A 3px mis-tap on a tag falls through to the card overlay and navigates to a post the user did not choose — an error they cannot anticipate and only discover after a page load.
*Fix:* Below 576px give `.card-tags a`, `.channels a` and `.now-source` transparent vertical padding to a 44px hit box, and raise `.write-btn` past 44px.
*Suggested command:* `/impeccable adapt`

**[P2] Design-system breaks a code reviewer will see.**
(a) Navbar and footer use Bootstrap's 1140px container while `main.container` is 760px, so the brand floats 190px (@1280) to 290px (@1920) left of every other element. (b) Light theme: card vs page is 1.05:1 (`#fefef8` on `#f8f8f2`) and archive hairline vs page is 1.22:1 — the "change of ground" DESIGN names as one of only two depth devices is imperceptible. (c) The light-theme primary button keeps `#ffb703` (1.64:1 at rest, 2.45:1 on hover, both under the 3:1 non-text minimum) while every other accent becomes `#8f5000` — two accent hues on screen at once, against the Single Filament Rule.
*Why it matters:* The misalignment is the one visible craft error on a page whose whole argument is craft, and it reads as untouched Bootstrap showing through — exactly what DESIGN's last "Don't" forbids.
*Fix:* Constrain navbar and footer containers to `--measure`. In light theme darken `--bs-tertiary-bg` toward `#efefe4` and `--bs-border-color` toward `#cfcfc0`, and set the button fill to `var(--link)` with paper text.
*Suggested command:* `/impeccable polish`

## Cognitive Load: HIGH — 5 of 8 checks fail

Failing: **single focus** (Now panel and pinned lead are both raised cards with the same amber left rule — the page marks "the leading thing" twice, confirmed independently by the detector's `side-tab` ×2); **chunking** (nav carries 6 items; each archive row carries 6 discrete elements); **visual hierarchy** (largest element is a writing-habit sentence, the role line is 11.52px, no `h1`); **minimal choices**; **progressive disclosure** (inverted — everything at equal weight, and the work comes last).

Passing: grouping, one thing at a time, working memory.

Decision points over the limit: top nav **6** (Posts, Topics, About, Write, Sign in, Dark ▾ — two are author-only, and `Write` is the only boxed, highest-contrast item in the nav); archive region **14 destinations** (5 titles + 9 tags); contact point **4 visible**, two of which resolve to the same URL. Page total: **33 focusable elements** on a page whose job is one decision.

## Emotional Journey

Entry is good — a greyscale photograph on Monokai ink reads as considered, and a real face is the right first beat for a trust decision. The peak arrives early and is well earned: conceding fallibility in the third sentence disarms an evaluator.

Then two valleys. Immediately after the peak the page drops from a person speaking at 3.15rem to a `dt`/`dd` readout in 11.5px service type, and the amber CTA arrives *there* — before the reader has been given one reason to want it. The archive is the second valley: four structurally identical rows, grey metadata, clamped grey summaries. The page gets quieter and greyer as you descend, the precise inverse of building conviction, with no further emotional beat anywhere.

The end violates peak-end outright: a copyright line and three grey words. Reassurance at the high-stakes moment is absent — no response-time expectation, no indication the button leaves for Telegram, no equal-weight alternative.

## Persona Red Flags

**Jordan (confused first-timer).** Reads `called_mad` in the navbar, `called_mad` again under the photo, and `IRYNA · BACKEND PYTHON` in 11.5px grey — he does not know whose site this is or what it is for. `NOW / UPDATED 28 JUL 2026` assumes prior exposure to the "now page" convention; `BUILDING / NEXT / SOURCE` have no group label. `DARK ▾` is a bare state word with a caret and no noun. `WRITE` is the only boxed, highest-contrast item in the nav — he reads it as an invitation to him and clicks into a live post editor. `READ →` looks like a button but is a `<span>`, not focusable, working only because an invisible overlay covers the card.

**Riley (deliberate stress tester).** `Sign in` renders a complete form labelled "Not wired up yet — arrives with JWT auth" — a shipped, top-nav-linked, non-functional form on a work sample. `Write` opens a live editor with no authentication: he can create, edit, pin and delete on the author's running site. View-source: `og:url=""`, `og:image=""`, `og:image:alt=""`, no `og:description`, no `twitter:card` — he shares the link into Slack or Telegram (which PRODUCT names as an arrival path) and gets a bare unfurl, while the template's own better fallback description at `layout.html:14` is never used on home. Heading outline: zero `h1`, five `h2`. Tab from the top: 11 stops before the first content link, no skip link. At 1920 the brand sits 290px left of the content. In light theme `WRITE TO ME` is amber while `NOW`, `PINNED`, `READ →` and the repo link are all brown — and `main.css:65` comments that warm Monokai accents are unreadable on light, which the button alone ignores.

**Casey (distracted mobile user).** At 375×812 her first screen ends inside the Now panel with zero post titles; the first one needs a scroll to 989px. `WRITE TO ME` sits 66px from the bottom edge as the only obvious action — she taps it and lands in Telegram having read none of the work, so the site's one conversion fires with zero evidence delivered. Wanting email instead, she must hit a 40×20px grey word that launches a mail client rather than handing her a string to paste into an ATS. On the archive she aims at `#python` (48×20) and misses by 3px onto the card overlay, landing on a post she did not pick. Excerpts clamped to two lines of grey serif read as a band she skips.

## Minor Observations

- `alt="{{ site.handle }}"` on the hero avatar duplicates the `called_mad` text beside it; a screen reader says the handle twice.
- `.stretched::after` prevents mouse-selecting titles, dates and excerpts — a recruiter pasting a title into a note has to work around it.
- No visited-link styling on `.post-title`; a returning evaluator cannot see which posts they already read.
- Five destinations open in new tabs with no external affordance.
- "Topics" (nav) and `#python` (cards) name one concept two ways.
- The hand-set `Updated 28 Jul 2026` is honest by design, but nothing degrades it — it becomes a liability the moment it is a month stale on the surface a recruiter judges for currency.
- DESIGN.md records Muted Sand at 6.17:1, which holds on `Ink`; where it is actually used, on `Raised Ink` in the Now panel and lead card, it measures 5.54:1. Still AA, but the recorded ratio does not match the real pairing — which matters given the Measured Contrast Rule.
- The pinned post is dated 18 Jul and sits above a 26 Jul post. Correctly labelled, but a skimmer's first impression of freshness is eight days behind reality.
- Archive dividers measure 1.51:1 dark, 1.22:1 light, and they carry the entire list structure per the Hairline-Over-Box Rule.
- No console errors. Bootstrap collapse, theme persistence, the title wipe and the `prefers-reduced-motion` block all behave correctly.

## Questions to Consider

1. If you deleted the Now panel entirely and put the pinned post-mortem directly under the hero sentence, what would actually be lost — and would a recruiter notice, or would they simply reach the evidence 450px sooner?
2. PRODUCT Principle 3 is "make invisible backend work visible," yet nothing on this page is produced by the backend it advertises. What single true, measured fact from this app's own runtime belongs here?
3. The amber CTA sends a hiring manager into Telegram before they have read one sentence of the work. Is contact the job of this page, or of the post page — and if it is the post page, why is the loudest element on home a contact button?
4. Substitute the photograph, the handle and the five titles for a designer's, and this composition works unchanged. What is the one structural decision on this page that a designer's portfolio could not steal?
