---
target: about page
total_score: 24
max_score: 28
na_heuristics: 5,7,9
p0_count: 1
p1_count: 1
timestamp: 2026-08-06T11-25-43Z
slug: templates-about-html
---
Method: dual-agent (A: design-review · B: detector-evidence)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | `aria-expanded`/Show-Hide word swap on `.faq-trigger` gives clear feedback; low ceiling on a static page |
| 2 | Match System / Real World | 4 | FAQ answers are plain and direct — "no license attached yet... Ask first," no evasive phrasing |
| 3 | User Control and Freedom | 4 | Accordion re-collapses, back-link returns home, no traps |
| 4 | Consistency and Standards | 2 | Internal contradiction (MySQL vs PostgreSQL), inconsistent repo-link text, masthead uses a type-scale token DESIGN.md scopes to the front page only |
| 5 | Error Prevention | n/a | Read-only page — no forms, no destructive actions |
| 6 | Recognition Rather Than Recall | 4 | Every section is self-contained; nothing requires remembering an earlier part of the page |
| 7 | Flexibility and Efficiency | n/a | No power-user path exists or is needed on a static bio+FAQ page |
| 8 | Aesthetic and Minimalist Design | 3 | On-system elsewhere, but the page's biggest visual gesture is spent on a handle already shown in the navbar one line above |
| 9 | Error Recovery | n/a | No error states exist — no input, nothing to fail |
| 10 | Help and Documentation | 4 | The FAQ is unusually well-scoped — it even explains the site's own visual design |
| **Total** | | **24/28** | **Good (85.7%)** |

## Design Specificity Verdict

**LLM assessment:** Grounded, with one self-inflicted wound. The bio names three specific failure modes that map to actual published posts, and the FAQ asks exactly what a technically literate evaluator would ask of *this* artifact — "What database does this run on?", "Can I reuse the code?", "Why does this look like a code editor?" — not generic portfolio filler. That's real specificity. Working against it: the masthead is styled identically to the front-page hero treatment despite carrying far less information, and the page states its own database as MySQL in one section and PostgreSQL in another, on the same screen — for a site whose pitch is "the implementation is the argument," that's the one place the page reads like it wasn't checked.

**Deterministic scan:** Assessment B ran the bundled detector against `templates/about.html`, `templates/_masthead.html`, and `templates/_contact.html` — **0 findings, clean.** No generic-SaaS/AI-slop patterns detected. This doesn't conflict with the issues above; the detector catches pattern-level slop (gradients, shadows, boilerplate copy), not content-level facts like a stat contradicting itself across two sections, or a design token used outside its documented scope — those require the LLM read, and neither is the kind of thing this detector class is built to catch.

**Visual overlays:** Not available — no browser-automation tool was exposed in this session, and both assessments independently confirmed this rather than approximating it. Assessment A additionally noted its own WebFetch attempt against the local dev server failed on a protocol mismatch (the tool force-upgrades to HTTPS; the dev server is plain HTTP), so even the structural fallback came from Assessment B's `curl` pull, not A's own view of the rendered page. Layout, spacing, and color judgment below is inferred from CSS source and DESIGN.md's stated tokens, not observed.

## Overall Impression

The content is the strongest thing on the page — the FAQ in particular does real work a generic "About" page wouldn't. The weakest thing is that the page doesn't fully trust that content: it spends its largest typographic gesture on a handle already visible in the navbar, and it contains a factual contradiction about its own stack that undercuts the site's core "the implementation is the argument" claim, right on the page most likely to be read by someone checking that claim.

## What's Working

- **The FAQ questions are product-specific, not template filler.** "Is there an RSS feed?", "Why does this look like a code editor?" are exactly what a technical evaluator of *this* artifact would ask. Q5 turning the site's own aesthetic into content is a genuinely good move.
- **The Show/Hide state indicator follows the project's own Named-State Rule.** `.faq-icon::before { content: "Show"/"Hide" }`, colored in the accent only when expanded — a word, not a rotating chevron. Assessment B independently confirmed the underlying markup is wired correctly: every `.faq-trigger` carries `type="button"`, `aria-expanded`, `aria-controls` matching its target `id`, and accessible question text in a plain `<span>`.
- **The bio is falsifiable, not descriptive.** It names three specific technical failures rather than asserting generic competence, directly serving the site's own stated principle that "a shortcut in the code is a shortcut in the portfolio."

## Priority Issues

**[P0] The page states two different databases for itself.** The stack table's "Data" row says `MySQL, pandas, NumPy`; the FAQ answers "What database does this run on?" with "PostgreSQL... the schema is in the repository, not a claim" — both visible within a few seconds of scanning the same page. *(Pre-existing: the MySQL row predates this session's FAQ work — PRODUCT.md already logs it as a known, deliberate loose end. Adding the FAQ answer is what turned it from a quiet gap into an on-page contradiction.)*
**Why it matters:** The primary audience PRODUCT.md names — a technical hiring manager evaluating in a minute or two — reads this as a direct contradiction right where the page is trying hardest to look precise. Not catchable by the detector; this is a content-accuracy read only an LLM pass (or a human) makes.
**Fix:** Either make clear "Data" is a general-skills row, not a claim about this site (separate it further from "This site" than proximity alone), or replace MySQL with a database she'd stand behind being asked about.
**Suggested command:** `/impeccable clarify`

**[P1] The masthead uses a type-scale token DESIGN.md scopes to the front page only.** `.masthead-title` renders at `--display-hero` — the same size the real front-page hero deliberately avoids (it uses `.hero-statement` instead) — while the auth pages already correctly override this via `title_class="auth-title"` → `--display-page`. About, Topics, and the Tagged-filter view don't. *(Pre-existing: this is inherited from the original copy-pasted `.masthead` markup on every page; the `_masthead.html` macro extracted earlier this session preserved the existing sizing rather than changing it — a legitimate scope call at the time, but it's now visible as a specificity gap.)*
**Why it matters:** The page's single biggest visual gesture is spent re-stating a handle already visible in the fixed navbar brand one line above, instead of on the bio/photo that actually differentiates this page.
**Fix:** Pass `title_class="auth-title"` (or add a `.masthead-title--page` mapped to `--display-page`) into the `head.masthead(...)` calls for About, Topics, and the tag-filtered view — matching what auth pages already do.
**Suggested command:** `/impeccable typeset`

**[P2] The FAQ has no heading landmark, confirmed structurally.** Assessment B's raw HTML pull shows the heading sequence jumps `<h1 class="masthead-title">` straight to five consecutive `<h3 class="faq-question">` tags with no `<h2>` in between. `.section-rule` (used for the "FAQ" label) renders as a `<p>`, not a heading, sitewide.
**Why it matters:** A screen-reader user navigating by heading level gets no announced "FAQ" landmark — they land inside question 1 with no section context. This is deterministic (B measured the actual tag sequence), not a subjective read.
**Fix:** Promote `.section-rule` to `<h2>` (visually unchanged, same class) or add a visually-hidden `<h2>` before the FAQ list.
**Suggested command:** `/impeccable harden`

**[P2] Five simultaneous FAQ options exceed the ≤4 guideline for one decision point.** No item is open by default; a reader has to scan all 5 labels before picking one.
**Why it matters:** For a reader evaluating "in a minute or two" (PRODUCT.md's stated context), that's a beat of friction progressive disclosure doesn't fully offset.
**Fix:** "Is there an RSS feed?" and "Can I comment on a post?" are both one-line "not built, do X instead" answers — merge into "What's not built yet?" to bring the visible set to 4.
**Suggested command:** `/impeccable distill`

**[P3] A typo and an inconsistent link-text convention, both pre-existing.** "This site" row reads "Asyncronous funcs" (missing the h); the repo link reads `OstapchukIryna/fastapi-blog` in the stack table but plain "GitHub" in FAQ Q2, for the identical URL. Assessment B confirmed 0 inline styles and 0 hardcoded hex outside `<head>` on this page — so this is the one loose end, not a pattern.
**Why it matters:** This is a work sample judged by exactly the kind of reader trained to notice a typo in the row describing this exact codebase.
**Fix:** Correct the typo; standardize on one link-text convention for `site.repo`.
**Suggested command:** `/impeccable polish`

## Persona Red Flags

**Alex (impatient power user) — skimming the bio to decide if it's worth reading further, in under 10 seconds.**
Before reaching a single sentence of bio, Alex parses a masthead block (eyebrow + up to 4.25rem title + tagline, 4.5rem top padding) to learn only "called_mad" — a handle already seen in the navbar brand one line above. The full name that would let Alex map this to a CV sits in the small tagline, not the huge title.

**Riley (deliberate stress tester) — reads every word, cross-checks every claim.**
Catches the MySQL/PostgreSQL contradiction (P0) and the "Asyncronous" typo (P3) directly. Also notices FAQ Q2 ("Can I reuse the code?") doesn't point to the contact section the way Q4 does, even though both answers imply the reader might need to reach out — an inconsistency in how the page signals "what to do next" between two structurally similar answers.

**Sam (accessibility-dependent, screen reader/keyboard-only) — opening an FAQ answer.**
Positive: the trigger is a real `<button>` inside an `<h3>`, Bootstrap's collapse JS toggles `aria-expanded` natively — keyboard activation and focus both work with no custom JS, confirmed structurally by Assessment B. Red flag: `.faq-icon` (the visual "Show"/"Hide" word) carries `aria-hidden="true"`, so the one piece of copy explaining the interaction is sighted-only — not a functional break since `aria-expanded` is announced independently, but redundant-by-design rather than redundant-by-accident. Bigger red flag: no heading precedes the FAQ list (P2), so heading-based navigation skips the section and lands Sam inside question 1 with zero context.

## Minor Observations

- The `.section-rule`-then-hairline pattern (label with a trailing rule, immediately followed by a list item with its own `border-top`) is a sitewide idiom, not About-specific — but it sits close to DESIGN.md's own "don't put two hairlines within a couple of centimetres of each other" rule; worth a second look sitewide rather than a local fix.
- `write_button()`'s "not configured yet" fallback is unreachable on About since `site.email` is always set — fine as defensive code.
- The contact block itself respects the ≤4-choices guideline the FAQ doesn't: one primary button plus two secondary links.
- Assessment B additionally confirmed: the page's one `<img>` has a proper `alt` attribute and explicit dimensions; other nav buttons (theme dropdown, sign out) lack `aria-expanded` — but those live in the shared `layout.html` navbar, not About specifically, so out of scope for this critique.

## Questions to Consider

- If the front page already solved "a bare handle means nothing to a stranger" by pairing it with avatar + role + name, why does About's masthead reintroduce the exact problem that fix was built to avoid?
- The FAQ's best moment is answering "why does this look like a code editor" — so why does the page's own biggest visual decision (the oversized masthead) go unexplained by that same self-aware voice?
- PRODUCT.md already logs the MySQL/PostgreSQL mismatch as a known, undecided fact rather than a defect — is About, read by exactly the audience trained to catch inconsistencies, the right page to leave it unresolved on?
