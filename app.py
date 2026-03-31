from flask import Flask, render_template, request, redirect, url_for
import requests
import mysql.connector

app = Flask(__name__)

SONAR_URL = "http://3.80.138.17:9000"
TOKEN = "squ_4f7ac18302a201ff8063adbbe59d1c2f8bdb4307"

DB = {
    "host": "localhost",
    "user": "root",
    "password": "Admin123",
    "database": "sonar_dashboard"
}

def db_conn():
    return mysql.connector.connect(**DB)


# -------- FETCH PROJECTS -------- #
def fetch_projects():
    try:
        r = requests.get(f"{SONAR_URL}/api/projects/search", auth=(TOKEN, ""))
        return r.json().get("components", [])
    except:
        return []


# -------- FETCH METRICS -------- #
def fetch_metrics(project_key):
    try:
        params = {
            "component": project_key,
            "metricKeys": "bugs,vulnerabilities,code_smells,coverage,duplicated_lines_density"
        }
        r = requests.get(f"{SONAR_URL}/api/measures/component", params=params, auth=(TOKEN, ""))

        data = r.json()
        metrics = {}

        for m in data.get("component", {}).get("measures", []):
            metrics[m["metric"]] = float(m.get("value", 0))

        return metrics
    except:
        return {}


# -------- FETCH QUALITY -------- #
def fetch_quality(project_key):
    try:
        r = requests.get(
            f"{SONAR_URL}/api/qualitygates/project_status",
            params={"projectKey": project_key},
            auth=(TOKEN, "")
        )
        return r.json().get("projectStatus", {}).get("status", "UNKNOWN")
    except:
        return "UNKNOWN"


# -------- FETCH RATINGS -------- #
def fetch_ratings(project_key):
    try:
        params = {
            "component": project_key,
            "metricKeys": "reliability_rating,security_rating,sqale_rating"
        }
        r = requests.get(f"{SONAR_URL}/api/measures/component", params=params, auth=(TOKEN, ""))

        data = r.json()

        rating_map = {"1.0": "A", "2.0": "B", "3.0": "C", "4.0": "D", "5.0": "E"}
        ratings = {}

        for m in data.get("component", {}).get("measures", []):
            ratings[m["metric"]] = rating_map.get(m.get("value", ""), "N/A")

        return ratings
    except:
        return {}


# -------- FETCH ISSUES -------- #
def fetch_issues(project_key):
    try:
        r = requests.get(
            f"{SONAR_URL}/api/issues/search",
            params={"componentKeys": project_key, "ps": 10},
            auth=(TOKEN, "")
        )
        return r.json().get("issues", [])
    except:
        return []


# -------- SAVE DATA -------- #
def save_data(project_key, metrics, quality, ratings, issues):
    conn = db_conn()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO metrics(project_key, bugs, vulnerabilities, code_smells, coverage, duplicated_lines)
    VALUES (%s,%s,%s,%s,%s,%s)
    """, (
        project_key,
        metrics.get("bugs", 0),
        metrics.get("vulnerabilities", 0),
        metrics.get("code_smells", 0),
        metrics.get("coverage", 0),
        metrics.get("duplicated_lines_density", 0)
    ))

    cur.execute(
        "INSERT INTO quality_gate(project_key, status) VALUES (%s,%s)",
        (project_key, quality)
    )

    cur.execute("""
    INSERT INTO ratings(project_key, reliability, security, maintainability)
    VALUES (%s,%s,%s,%s)
    """, (
        project_key,
        ratings.get("reliability_rating", "N/A"),
        ratings.get("security_rating", "N/A"),
        ratings.get("sqale_rating", "N/A")
    ))

    for issue in issues:
        cur.execute("""
        INSERT INTO issues(project_key, issue_key, severity, message, file, line)
        VALUES (%s,%s,%s,%s,%s,%s)
        """, (
            project_key,
            issue.get("key"),
            issue.get("severity"),
            issue.get("message"),
            issue.get("component"),
            issue.get("line", 0)
        ))

    conn.commit()
    cur.close()
    conn.close()


# -------- ROUTES -------- #

@app.route("/", methods=["GET", "POST"])
def dashboard():
    projects = fetch_projects()
    selected_project = request.form.get("project")

    metrics = quality = ratings = issues = None

    if selected_project:
        conn = db_conn()
        cur = conn.cursor(dictionary=True)

        cur.execute("SELECT * FROM metrics WHERE project_key=%s ORDER BY id DESC LIMIT 1", (selected_project,))
        metrics = cur.fetchone()

        cur.execute("SELECT * FROM quality_gate WHERE project_key=%s ORDER BY id DESC LIMIT 1", (selected_project,))
        quality = cur.fetchone()

        cur.execute("SELECT * FROM ratings WHERE project_key=%s ORDER BY id DESC LIMIT 1", (selected_project,))
        ratings = cur.fetchone()

        cur.execute("SELECT * FROM issues WHERE project_key=%s ORDER BY id DESC LIMIT 10", (selected_project,))
        issues = cur.fetchall()

        cur.close()
        conn.close()

    return render_template("dashboard.html",
                           projects=projects,
                           selected_project=selected_project,
                           metrics=metrics,
                           quality=quality,
                           ratings=ratings,
                           issues=issues)


@app.route("/fetch/<project_key>")
def fetch_store(project_key):
    metrics = fetch_metrics(project_key)
    quality = fetch_quality(project_key)
    ratings = fetch_ratings(project_key)
    issues = fetch_issues(project_key)

    save_data(project_key, metrics, quality, ratings, issues)

    return redirect(url_for('dashboard'))


if __name__ == "__main__":
    app.run(debug=True)