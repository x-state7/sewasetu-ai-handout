#The dashboard intentionally shows no claimed test results before actual evaluations run.
"""Public read-only evaluation dashboard.

Publish synthetic personas and reviewed,
redacted conversation reports only.
"""

import json
import os
import re
from pathlib import Path

from flask import Flask, render_template_string


app = Flask(__name__)

REPORT_DIR = Path(
    os.environ.get(
        "EVAL_REPORT_DIR",
        "/var/sewasetu/eval-public",
    )
)

PAGE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Seva Setu — Agent Evaluations</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body {
    font: 16px system-ui,sans-serif;
    max-width: 900px;
    margin: 3rem auto;
    padding: 0 1rem;
    color: #202838;
}
section {
    border: 1px solid #ddd;
    border-radius: 8px;
    padding: 1rem;
    margin: 1rem 0;
}
.pass { color: #087b3c; }
.fail { color: #ac2424; }
pre { white-space: pre-wrap; word-break: break-word; }
</style>
</head>
<body>

<h1>Seva Setu — MCP Evaluation</h1>

<p>
Fictional citizens, conversations, observed outcomes,
and database assertions.
</p>

{% if reports %}
<p>Recent verified evaluation runs (newest first). Only genuinely executed reports are shown.</p>
{% for report in reports %}
<section>
<h2>Run {{ report.run_id }}</h2>
<p>Environment: {{ report.environment | default('Not specified', true) }}</p>
<p>
Run: {{ report.run_id }} |
{{ report.created_at }}
</p>

<p>
Verified live agent + MCP + PostgreSQL run: {{ report.model }}.
Passed {{ report.summary.passed }}
of {{ report.summary.total }};
pass rate {{ report.summary.pass_rate }}%
</p>

{% for item in report.results %}
<section>
<h2>{{ item.id }} — {{ item.persona }}</h2>

<p><b>Goal:</b> {{ item.prompt }}</p>
<p><b>Tool:</b> {{ item.tool }}</p>

<p>
<b>Database verification:</b>
<span class="{{ 'pass' if item.status == 'PASS' else 'fail' }}">
{{ item.status }}
</span>
— {{ item.reason }}
</p>

{% if item.conversation %}
<details>
<summary>Redacted test conversation</summary>
{% for turn in item.conversation %}
<p>{{ turn }}</p>
{% endfor %}
</details>
{% endif %}

</section>
{% endfor %}
</section>
{% endfor %}

{% else %}
<p>
No real evaluation reports published yet.
No passes claimed.
</p>
{% endif %}

</body>
</html>
"""


def published_reports(limit=10):
    if REPORT_DIR.is_symlink() or not REPORT_DIR.exists():
        return []

    paths = sorted(
        (
            p for p in REPORT_DIR.glob("eval-*.json")
            if p.is_file()
            and not p.is_symlink()
            and re.fullmatch(
                r"eval-[a-f0-9]{32}\.json",
                p.name,
            )
            and p.stat().st_size <= 300_000
        ),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    result = []
    for path in paths:
        try:
            report = json.loads(
                path.read_text(encoding="utf-8")
            )

            if (
                report.get("mode") == "live_agent_db_verified"
                and isinstance(report.get("results"), list)
                and isinstance(report.get("summary"), dict)
            ):
                result.append(report)
                if len(result) >= limit:
                    break

        except (OSError, ValueError, AttributeError):
            continue

    return result


def latest():
    """Backward-compatible single-run accessor."""
    result = published_reports(limit=1)
    return result[0] if result else None


@app.get("/eval-dashboard")
def dashboard():
    return (
        render_template_string(
            PAGE,
            reports=published_reports(),
        ),
        200,
        {
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": (
                "default-src 'none'; "
                "style-src 'unsafe-inline'"
            ),
        },
    )
