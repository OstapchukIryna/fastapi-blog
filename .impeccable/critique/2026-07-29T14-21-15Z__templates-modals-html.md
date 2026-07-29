---
target: the success and error popups
total_score: 20
max_score: 36
na_heuristics: 10
p0_count: 1
p1_count: 3
timestamp: 2026-07-29T14-21-15Z
slug: templates-modals-html
---
Method: dual-agent (A: a78de748be240a101 · B: aa4310b4759bfc519)

Target: the shared success and error result popups — `templates/_modals.html`, consumed by `post_form.html` and `profile.html` via `static/js/utils.js`.
Mode: Operate. Surface: server-rendered Jinja + Bootstrap 5.3, no build step.

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 2 | No in-flight state; a long POST is silent except the button dimming. |
| 2 | Match System / Real World | 3 | Dialog titled "Saved" when the event was *published* or *deleted*. |
| 3 | User Control and Freedom | 2 | Button says "Close"; it actually navigates. |
| 4 | Consistency and Standards | 1 | Five of six dialog buttons ignore the system button spec (Newsreader 16px / 38px vs mono 12.8px / 44px). |
| 5 | Error Prevention | 3 | Delete is gated and quotes the title, but the double-submit guard hangs off `event.submitter`, which is null on Enter-submit. |
| 6 | Recognition Rather Than Recall | 2 | Names three fields, then covers them. |
| 7 | Flexibility and Efficiency | 2 | Focus lands on the container; two Tabs to the only action. |
| 8 | Aesthetic and Minimalist Design | 3 | Genuinely restrained, but three rules frame one sentence. |
| 9 | Error Recovery | 2 | Diagnosis good; recovery absent — no focus move, no retry, failed delete discards the confirmation. |
| 10 | Help and Documentation | n/a | A two-line outcome dialog has no documentation surface. |
| **Total** | | **20/36** | **Acceptable (56%)** |

## Design Specificity Verdict

Authored chrome bolted onto stock Bootstrap controls, and the seam was visible. Authored: the Deep Ink surface, hairline header/footer, Space Grotesk titles at `--text-lg`, and colouring the title by outcome instead of shipping an icon — with the reason recorded in the stylesheet. Not authored: the controls. Exactly one of six buttons obeyed the system's own button spec.

Deterministic scan: `detect.mjs` returned 1 finding across `templates/` — `overused-font` (Space Grotesk) at `layout.html:30`, site-wide and unrelated to the modals. Zero static findings in `_modals.html`, `post_form.html`, `profile.html`. The browser overlay added two `all-caps-body` findings on `/profile`, both on `.field-hint.mono-label` strings of 78 and 35 characters — long prose wearing a service-string style.

## Priority Issues

### [P0] Failed delete left the page in a dead end
`hideModal(closes)` and `show()` ran in the same tick. Bootstrap counts one backdrop and one scroll lock per open dialog and does that bookkeeping across the transition, so the confirmation stayed on screen with two backdrops behind it, `body` kept `overflow: hidden`, and `.modal-footer` intercepted clicks at the centre of the viewport. Verified: `scrollBy(0,500)` left `scrollY` at 0. Only a reload escaped.

Root cause runs deeper than the same-tick call: `hide()` is ignored outright while a dialog is still animating in, and an ignored hide emits no `hidden.bs.modal`. Instrumented timeline showed `show` at 3ms, `shown` at 1987ms, and a `hide()` at 1109ms doing nothing at all.

### [P1] Focus dumped on `<body>` when either window closed
A modal shown from script has no `relatedTarget`, so Bootstrap restored nothing. A keyboard user who had just failed validation was teleported to the top of the document and had to Tab through the whole navbar to reach the field they were told to fix.

### [P1] The success window's only button lied about what it did
`Close` was hardcoded; closing ran `location.assign()`. Brand commitment in PRODUCT.md: "Buttons say what happens."

### [P1] Five of six dialog buttons ignored the system's button spec
Measured Newsreader 16px, Title Case, 38px tall — Bootstrap's untouched `--bs-btn-font-size`. 16px is not a step on the ramp. `.btn-close` was 33×33 against the same 44px floor the stylesheet enforces elsewhere with a comment.

### [P2] Wrong nouns on the destructive path
Deleting produced "Saved — Post … deleted." A failed delete produced "Not saved" with "Back to the form" after the form had been removed. A shared component never re-read against its third consumer.

### [P2] Two `all-caps-body` findings on /profile
78- and 35-character sentences set in the uppercase mono label style. The site's own Mono-Label Rule covers service strings; these were prose.

## Persona Red Flags

**Sam (screen reader / keyboard)**: no `aria-describedby`, so the message was never announced — only the heading. `role="dialog"` where an interrupting failure wants `alertdialog`. No `aria-invalid`: the rose border was colour alone. 33px close target.

**Riley (stress tester)**: double-submit unguarded on Enter-submit (`event.submitter` is null). Network failure offered "try again" and only a dismiss. Two backdrops for ~150ms even on the paths that recovered.

**Hiring manager (PRODUCT.md's primary audience, auditing this as a work sample)**: "They wrote a design system and then didn't follow it on the last screen." DESIGN.md specifies the button typeface and a 44px floor; the dialogs shipped Bootstrap's serif at 38px. A reviewer finds that in ninety seconds, and a spec the author's own code ignores is worse evidence than no spec.

## Minor Observations

- Only the success button got `.write-btn` — the asymmetry is the tell that the error path was built second.
- `[data-bs-theme="light"] --overlay: #272822` is unreachable: its only consumer sits inside a subtree forced to dark. Dead token in a system whose headline rule is Token-Only.
- `describeFieldErrors` reads `label.textContent`, so the dialog says "Title" while the rendered label says "TITLE".

## Questions to Consider

1. Why is there a dialog on success at all? The destination page could carry the outcome in the accent — which is what the Named-State Rule already prescribes.
2. If the error dialog's only job is to point at fields, why isn't it the fields? The server-rendered path renders `.form-summary` in place; the enhanced path replaced that with a box covering the same information.
3. The delete confirmation is authored; the delete failure was not. Which one is the work sample?
