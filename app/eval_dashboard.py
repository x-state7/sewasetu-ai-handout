
"""Private, read-only Seva Setu evaluation dashboard."""

import hmac
import json
import os
import re

from pathlib import Path

from flask import Flask, Response, abort, render_template_string, request


app = Flask(__name__)

REPORT_DIR = Path(
    os.getenv("EVAL_REPORT_DIR", "/var/sewasetu/eval-reports")
)

DASHBOARD_HTML = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Seva Setu Evaluation Dashboard</title>
<style>
body {
    font-family: system-ui, sans-serif;
    background: #f8fafc;
    color: #18212f;
    margin: 0;
    padding: 32px;
}
main { max-width: 1080px; margin: auto; }
h1 { font-size: 28px; margin-bottom: 5px; }
.subtitle { color: #64748b; }
.cards {
    display: grid;
    grid-template-columns: repeat(auto-fit,minmax(140px,1fr));
    gap: 12px;
    margin: 25px 0;
}
.card, .panel {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 18px;
}
.value { font-size: 27px; font-weight: 700; }
.label { color: #64748b; font-size: 13px; }
table {
    width: 100%;
    border-collapse: collapse;
    background: white;
}
th, td {
    padding: 12px;
    text-align: left;
    border-bottom: 1px solid #e2e8f0;
    font-size: 13px;
}
th { background: #f1f5f9; }
.PASS { color: #167347; font-weight: 700; }
.FAIL,.ERROR { color: #a52424; font-weight: 700; }
.small { font-size: 12px; color: #64748b; }
a { color: #1d4ed8; }
</style>
</head>
<body>
<main>
<h1>Seva Setu — MCP Evaluation</h1>
<p class="subtitle">Private deployment verification dashboard</p>

{% if report %}
<p class="small">
    Run: {{ report.run_id }} |
    Generated: {{ report.created_at }}
</p>

<div class="cards">
    <div class="card"><div class="label">Total</div>
      <div class="value">{{ report.summary.total }}</div></div>
    <div class="card"><div class="label">Passed</div>
      <div class="value">{{ report.summary.passed }}</div></div>
    <div class="card"><div class="label">Failed</div>
      <div class="value">{{ report.summary.failed }}</div></div>
    <div class="card"><div class="label">Errors</div>
      <div class="value">{{ report.summary.errors }}</div></div>
    <div class="card"><div class="label">Pass rate</div>
      <div class="value">{{ report.summary.pass_rate }}%</div></div>
</div>

<div class="panel">
<h2>Scenario results</h2>
<table>
<thead><tr>
    <th>ID</th><th>Persona</th><th>Tool</th>
    <th>Result</th><th>Explanation</th>
</tr></thead>
<tbody>
{% for row in report.results %}
<tr>
    <td>{{ row.id }}</td>
    <td>{{ row.persona }}</td>
    <td>{{ row.tool }}</td>
    <td class="{{ row.status }}">{{ row.status }}</td>
    <td>{{ row.reason }}</td>
</tr>
{% endfor %}
</tbody>
</table>
</div>

{% else %}
<div class="panel">
<h2>No evaluation reports available</h2>
<p>Run the deployment evaluation to generate the first report.</p>
</div>
{% endif %}

</main>
</body>
</html>
"""


def authorized():
    username = os.getenv("EVAL_DASHBOARD_USERNAME", "")
    password = os.getenv("EVAL_DASHBOARD_PASSWORD", "")

    if not username or not password or len(password) < 24:
        return False

    credentials = request.authorization
    if credentials is None or credentials.type.lower() != "basic":
        return False

    return (
        hmac.compare_digest(credentials.username or "", username)
        and hmac.compare_digest(credentials.password or "", password)
    )


@app.before_request
def protect_dashboard():
    if not authorized():
        return Response(
            "Authentication required",
            401,
            {
                "WWW-Authenticate": 'Basic realm="Seva Setu Evaluation"',
                "Cache-Control": "no-store",
            },
        )


@app.after_request
def security_headers(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'unsafe-inline'"
    )
    return response


def latest_report():
    if not REPORT_DIR.exists():
        return None

    if REPORT_DIR.is_symlink():
        return None

    reports = sorted(
        (
            p for p in REPORT_DIR.iterdir()
            if p.is_file()
            and not p.is_symlink()
            and re.fullmatch(
                r"eval-[0-9a-f]{32}\\.json", p.name
            )
            and p.stat().st_size <= 512_000
        ),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    for path in reports:
        try:
            with path.open("r", encoding="utf-8") as file:
                data = json.load(file)

            if (
                isinstance(data, dict)
                and isinstance(data.get("summary"), dict)
                and isinstance(data.get("results"), list)
            ):
                return data
        except (OSError, ValueError):
            continue

    return None


@app.route("/eval-dashboard", methods=["GET"])
def dashboard():
    return render_template_string(
        DASHBOARD_HTML,
        report=latest_report(),
    )
