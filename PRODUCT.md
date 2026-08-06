# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary, and the ones to optimise for when interests diverge:

- **Hiring managers, recruiters and technical interviewers** evaluating Iryna as
  a backend candidate. They arrive from a CV, a job application or a GitHub
  profile, look briefly, and are deciding whether she is worth an interview.
- **Potential freelance clients** evaluating her for a specific job. They are
  judging reliability and stack fit.

Both arrive to form a judgement quickly, not to read.

Secondary, real but not optimised for: developers who arrive from a search
engine with the same bug and read one post for the answer.

## Product Purpose

A personal site whose subject is backend engineering skill. Iryna builds it in
public, and the site itself is the primary work sample rather than a container
describing work done elsewhere.

Success, as of 2026-07-28: the site leads to interviews for backend positions.
Reputation and audience are welcome side effects, not the goal.

## Positioning

Most portfolio sites describe engineering done somewhere else, and the reader
has to take the description on trust. Here the deliverable and the demonstration
are the same public repository: what the visitor is looking at is the artefact
being judged, and its source is open next to it.

The writing carries the second half of the claim. Every post is a post-mortem of
the author's own mistake — the GIL refusing to help, a validator silently
returning `None`, a window function that cannot be filtered in `WHERE`, a dict
paying for a resize. They demonstrate how she reasons about failure, which is
the thing an interviewer actually wants to know and the thing a list of
technologies cannot show.

## Operating Context

- Visitors usually arrive from a link — a CV, an application, a GitHub profile,
  a Telegram message — and evaluate in a minute or two.
- The source repository is part of the evaluation and is linked from the site:
  `https://github.com/OstapchukIryna/fastapi-blog`.
- Single author. Posts are authored as markdown, either as files under
  `content/` for seeded posts or through the site's own editor.
- The project is built alongside a video course, so capabilities arrive in
  course order rather than by product priority.

## Capabilities and Constraints

Built and working:

- Front page with a single pinned lead post and an archive list.
- Post page with tag-based recommendations and a reading-progress indicator.
- Tag index, per-tag listing, per-author listing, About, and error pages that
  split HTML and JSON responses by path.
- Full post management: create, edit, pin/unpin, delete, as server-rendered
  forms sharing the API's validation schema.
- JWT authentication: sign in, sign up, current-user resolution, and password
  reset by emailed token.
- Profile pictures: upload, replace and remove, validated before decoding.
- Read JSON API for posts, tags and users; post and user creation; pagination
  on every list.
- Alembic migrations, checked against model drift in CI.
- A pytest suite (three browser journeys, plus import-graph and layering
  checks) and a Postman API-contract suite (101 requests, 375 assertions),
  both run in CI.
- Light and dark themes, dark by default.
- CI on GitHub Actions: ruff, ruff format, djlint, pyrefly and a strict docs
  build; pytest against a real PostgreSQL database; the Postman collection as
  an API contract test; Alembic migrations checked against model drift.

Every item the course originally ordered — JWT authentication, file uploads,
pagination, Alembic migrations, pytest — is built. In progress: a `likes`
column exists on the post model (migration `e0cb386df82a`) but has no schema
field or endpoint yet. Also intended by the author: Docker deployment. The
application's I/O paths (routes, services, mail) are already async throughout.

Technical constraints, binding:

- Server-rendered templates, PostgreSQL, no build step, no frontend framework,
  and as few dependencies as possible, until something measured says
  otherwise. Every dependency added early is one that has to be kept alive.
- Python 3.14, uv, ruff, pyrefly.

Undecided product facts:

- The project description names MySQL, but the app runs on PostgreSQL and no
  move has been made to match the description. Treated as deliberate for now,
  not as a defect.

## Brand Commitments

- **`called_mad`** is the primary mark — a personal handle used for years, and an
  asset rather than a placeholder. The real first name **Iryna** appears as a
  supporting identity line, never as the large display name.
- The profile photograph is real, is already black and white in the original,
  and is used on her social accounts.
- **Voice: plain language, never marketing.** Buttons say what happens. Empty
  states say what to do next. No exclamation marks, no "seamless", no
  "powerful", no superlatives. If a sentence would embarrass her in a code
  review, it does not go in the interface either.
- **Language: English only.** This is a decision, not an accident; there is no
  Russian version planned.
- Colour changes only through CSS custom properties in `:root` and
  `[data-bs-theme]`. A component or template that hardcodes a hex value is a
  bug, because it is the one thing that cannot follow a theme switch.
- Code comments record why, not what. A comment that restates the line below it
  is noise.
- Contact channels: Telegram `@parzifay`, `blue.hunde@gmail.com`,
  `https://github.com/OstapchukIryna`.

## Evidence on Hand

- Five published posts with real technical content, sources under `content/`:
  threads versus processes and the GIL, the Pydantic validator that returns
  `None`, why a window function cannot be filtered in `WHERE`, what happens when
  a dict resizes, and replacing pip/black/mypy with uv/ruff/pyrefly.
- The public source of this site, linked from the front page and About.
- A real profile photograph in `static/profile_pics/`.
- A separate taste board application at `~/Projects/taste-board` (private repo
  `OstapchukIryna/taste-board`) holding her design constraints, idea sources and
  concrete references. `GET /api/pack` returns all of it in one response; the
  same data sits offline in its `data/*.json`. It is hand-maintained and is the
  authority on her taste.

Absences that future work must not fabricate: there are no testimonials, no
client work, no named employers, no case studies, no usage metrics and no
performance benchmarks. None of these may be invented to fill a layout.

## Product Principles

1. **The implementation is the argument.** The site is judged as a work sample,
   so anything claimed on the surface has to be true in the repository. A
   shortcut in the code is a shortcut in the portfolio.
2. **Optimise for a fast evaluator.** A hiring reader decides in a minute or
   two. Depth must be reachable but never required to form the judgement.
3. **Make invisible backend work visible.** Query design, correctness under
   concurrency and error handling are the subject matter. Work a visitor cannot
   perceive is work the portfolio is not getting credit for.
4. **Honest over impressive.** No fabricated proof, no decorative progress, no
   claim that outruns what is built. A number shown on the page must be measured.
5. **Boring stack until measured otherwise.** Reach for the plain option first;
   novelty has to earn its keep.

## Accessibility & Inclusion

Motion respects `prefers-reduced-motion`, and transitions exist to confirm that
something changed rather than to entertain. Keyboard focus is visible.

No formal standard has been committed to beyond this.
