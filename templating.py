from pathlib import Path

import markdown
from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).parent / "templates"

templates = Jinja2Templates(directory=TEMPLATES_DIR)

templates.env.filters["markdown"] = lambda text: markdown.markdown(
    text, extensions=["fenced_code", "tables"]
)
