"""Two front doors, one package each.

`api/` answers JSON and is described in /openapi.json. `web/` answers
pages and is excluded from that document. They are separate because their
needs diverged — form state, error wording, the arrangement of a front
page — and none of that is any use to the API.

What they have in common lives below, in services/, and that is the only
place either of them reads from: `web` imports nothing from `api`.
"""
