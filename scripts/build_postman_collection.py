"""
Build a Postman v2.1 collection from the workspace directory.

Postman's own on-disk format is a tree — one YAML file per request, one
per folder — which is what makes a change to a single test readable in
review. Newman only reads the single-file v2.1 JSON, so this converts
the one into the other.

The JSON is a build artifact and is deliberately not committed: the
workspace under postman/ is the source, and a second committed copy
would be a second thing to keep in step.

Usage:
    uv run python scripts/build_postman_collection.py [OUT.json]

Prints the path it wrote.
"""

import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
COLLECTIONS = ROOT / "postman" / "collections"
SCHEMA = "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"

# Postman writes the hook name with an "http:" prefix at collection level
# and without it on a request. Both mean the same listener.
LISTEN = {
    "afterResponse": "test",
    "http:afterResponse": "test",
    "beforeRequest": "prerequest",
    "http:beforeRequest": "prerequest",
}


def load(path: Path) -> dict[str, Any]:
    """Read one YAML document, tolerating an empty file."""
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def events(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Turn a `scripts:` list into collection `event` entries.

    Postman stores a script as one block of text; the v2.1 schema wants
    it split into lines under `exec`.
    """
    out = []
    for script in spec.get("scripts") or []:
        listen = LISTEN.get(script.get("type", ""))
        if listen is None:
            continue
        out.append(
            {
                "listen": listen,
                "script": {
                    "type": script.get("language", "text/javascript"),
                    "exec": script.get("code", "").split("\n"),
                },
            }
        )
    return out


def build_request(path: Path) -> dict[str, Any]:
    """Convert one `*.request.yaml` into a v2.1 item."""
    spec = load(path)
    url = spec.get("url", "")

    request: dict[str, Any] = {
        "method": spec.get("method", "GET"),
        # The schema also allows url as {host, path, ...}. Left as the
        # plain string on purpose: splitting it by hand sent every
        # request to {{baseUrl}} with the path silently dropped, and
        # Postman resolves the string form itself.
        "url": url,
    }
    if spec.get("description"):
        request["description"] = spec["description"]

    headers = spec.get("headers") or {}
    if headers:
        request["header"] = [{"key": k, "value": v} for k, v in headers.items()]

    body = spec.get("body")
    if body and body.get("content") is not None:
        if body.get("type") == "formdata":
            # The upload endpoint is the only one sending a file, and a
            # file cannot live in the collection: `src` is a path that
            # scripts/api-tests.sh writes and passes in.
            request["body"] = {"mode": "formdata", "formdata": body["content"]}
        else:
            request["body"] = {
                "mode": "raw",
                "raw": body["content"],
                "options": {"raw": {"language": body.get("type", "json")}},
            }

    item: dict[str, Any] = {
        "name": path.name.removesuffix(".request.yaml"),
        "request": request,
    }
    if evs := events(spec):
        item["event"] = evs
    return item


def ordered(paths: list[Path], key) -> list[Path]:
    """
    Sort by Postman's own `order`, falling back to the name.

    Order matters: the run creates a user, uses it, then deletes it, so
    a folder that ran out of turn would work on state that is not there
    yet.
    """
    return sorted(paths, key=lambda p: (load(key(p)).get("order", 0), p.name))


def build_folder(folder: Path) -> dict[str, Any]:
    """Convert one folder directory into a v2.1 item group."""
    spec = load(folder / ".resources" / "definition.yaml")
    requests = list(folder.glob("*.request.yaml"))

    item: dict[str, Any] = {
        "name": folder.name,
        "item": [build_request(p) for p in ordered(requests, lambda p: p)],
    }
    if spec.get("description"):
        item["description"] = spec["description"]
    return item


def build(source: Path) -> dict[str, Any]:
    """Convert a whole collection directory."""
    spec = load(source / ".resources" / "definition.yaml")

    folders = [d for d in source.iterdir() if d.is_dir() and d.name != ".resources"]

    collection: dict[str, Any] = {
        "info": {
            "name": spec.get("name", source.name),
            "description": spec.get("description", ""),
            "schema": SCHEMA,
        },
        "item": [
            build_folder(f)
            for f in ordered(folders, lambda d: d / ".resources" / "definition.yaml")
        ],
        "variable": [
            {"key": k, "value": v} for k, v in (spec.get("variables") or {}).items()
        ],
    }
    if evs := events(spec):
        collection["event"] = evs
    return collection


def main() -> int:
    sources = (
        [d for d in COLLECTIONS.iterdir() if d.is_dir() and (d / ".resources").is_dir()]
        if COLLECTIONS.is_dir()
        else []
    )

    if not sources:
        print(f"no collection found under {COLLECTIONS}", file=sys.stderr)
        return 1
    if len(sources) > 1:
        names = ", ".join(sorted(d.name for d in sources))
        print(f"expected one collection, found: {names}", file=sys.stderr)
        return 1

    collection = build(sources[0])
    out = (
        Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "postman" / "collection.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(collection, indent=2, ensure_ascii=False) + "\n")

    requests = sum(len(f["item"]) for f in collection["item"])
    print(f"{out}: {len(collection['item'])} folders, {requests} requests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
