from flask import Flask, request, jsonify, render_template_string
import argparse
import logging
from datetime import datetime

app = Flask(__name__)
logs = []
verbose = False  # Global variable to track verbosity

# Disable Flask's default request logging
log = logging.getLogger('werkzeug')
log.disabled = True

# Function to log requests with specified format
def log_request(route, method, query_value=None, body=None, log_only_in_cli=False):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Determine route display name
    if route == "/q":
        route_name = "[query]"
        log_entry = f"{route_name} {method} {timestamp}: {query_value if query_value is not None else ''}"
    else:
        route_name = "[root]" if route == "/" else f"[{route.strip('/')}]"
        log_entry = f"{route_name} {method} {timestamp}"
        if query_value:
            log_entry += f": {query_value}"

    # Append body if available
    if body:
        log_entry += f"\n{body}"

    # CLI log format
    logging.info(log_entry)
    
    # Web log format
    log_entry_web = log_entry.replace("\n", "<br>")  # Ensure line breaks for HTML
    if not log_only_in_cli:
        logs.append(log_entry_web)

# Root route
@app.route("/", methods=["GET", "POST"])
def home():
    data = ""  # / route should return an empty response
    log_request("/", request.method, body=data)
    return data

# Query parameter route
@app.route("/q", methods=["GET"])
def query():
    query_value = request.args.get("q", None)  # Get "q" parameter, None if not provided
    log_request("/q", request.method, query_value=query_value)
    return jsonify({"q": query_value})  # Return only the query value or empty if not provided

# Logs viewing route with simplified HTML and CSS styling
@app.route("/logs", methods=["GET"])
def get_logs():
    log_request("/logs", request.method, log_only_in_cli=True)  # Log only in CLI for /logs access
    
    # HTML template with simple CSS and dark mode support
    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Logs</title>
        <style>
            body { font-family: Arial, sans-serif; background: #f4f4f9; padding: 10px; color: #333; }
            .log-entry { background: #fff; border-radius: 8px; padding: 10px; margin: 8px 0; }
            @media (prefers-color-scheme: dark) {
                body { background: #1e1e1e; color: #ccc; }
                .log-entry { background: #333; color: #eee; }
            }
        </style>
    </head>
    <body>
        {% for log in logs %}
            <div class="log-entry">{{ log | safe }}</div>
        {% endfor %}
    </body>
    </html>
    """
    return render_template_string(html_template, logs=logs)

# Catch-all route for other paths
@app.route("/<path:subpath>", methods=["GET", "POST"])
def other_routes(subpath):
    data = request.get_json() if request.is_json else request.data.decode('utf-8')
    route_name = f"/{subpath}"
    log_request(route_name, request.method, query_value=subpath, body=data)
    return subpath  # Return only the path as the response

def main():
    global verbose
    parser = argparse.ArgumentParser(description="Receiver Web Server")
    parser.add_argument("-i", "--ip", default="0.0.0.0", help="IP address to bind")
    parser.add_argument("-p", "--port", type=int, default=80, help="Port number to bind")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("-V", "--version", action="version", version="Receiver Version 0.1.0", help="Show version")

    args = parser.parse_args()
    verbose = args.verbose

    # Configure logging level based on verbosity setting
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(message)s')  # Custom format without extra info

    # Run Flask application
    app.run(host=args.ip, port=args.port)

if __name__ == "__main__":
    main()
