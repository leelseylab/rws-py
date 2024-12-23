import argparse
import logging
import signal
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
from datetime import datetime
import http.client
import threading

# Global variables
logs = []
verbose = False

# Configure logging
def configure_logging(verbose):
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(message)s')

# Custom log handler
def log_request(route, method, query_value=None, body=None, log_only_in_cli=False, client_address=""):
    timestamp = datetime.now().strftime("%H:%M:%S %d-%m-%Y")
    # Determine route display based on verbose and whether it's root
    if route == "/":
        route_name = "" if not verbose else f"{client_address}/"
    else:
        route_name = route.lstrip("/") if not verbose else f"{client_address}/{route.lstrip('/')}"
    
    log_entry = f"[+] {timestamp} ({method}) {route_name}"

    if query_value:
        log_entry += f" - {query_value}"
    if body:
        log_entry += f"\n{body}"

    # CLI logging format
    logging.info(log_entry)

    # /logs logging format, exclude favicon and /logs itself from logs
    if not log_only_in_cli and route not in ["/favicon.ico", "/logs"]:
        log_entry_web = log_entry.replace("[+]", "").replace("\n", "<br>")
        logs.append(log_entry_web)

# Function to parse target URL and send HTTP request
def send_request_to_target(query, target):
    if not target.startswith("http://") and not target.startswith("https://"):
        target = "http://" + target
    try:
        target_parsed = urlparse(target)
        conn = (http.client.HTTPSConnection if target_parsed.scheme == "https" 
                else http.client.HTTPConnection)(target_parsed.netloc)
        path = target_parsed.path or "/"
        path += "?" + target_parsed.query if target_parsed.query else ""
        payload = json.dumps({"query": query}, separators=(",", ":"))
        
        conn.request("POST", path, body=payload, headers={"Content-Type": "application/json"})
        response = conn.getresponse()
        response_text = response.read().decode("utf-8")
        conn.close()
        return response_text
    except Exception as e:
        return f"Failed to request {target}: {e}"

# HTML template for log display
def generate_logs_html():
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Receiver Web Server</title>
        <style>
            body {{ font-family: Arial, sans-serif; background: #f4f4f9; padding: 10px; color: #333; }}
            .header, .footer {{ text-align: center; padding: 10px; }}
            .header {{ font-size: 24px; font-weight: bold; }}
            .log-entry {{ background: #fff; padding: 10px; margin: 8px 0; border-radius: 8px; }}
            #log-container {{ max-height: 70vh; overflow-y: auto; }}
            .refresh-btn {{ padding: 5px 10px; cursor: pointer; margin-top: 10px; }}
            @media (prefers-color-scheme: dark) {{
                body {{ background: #1e1e1e; color: #ccc; }}
                .log-entry {{ background: #333; color: #eee; }}
                .footer {{ color: #888; }}
                .refresh-btn {{ background-color: #444; color: #ccc; }}
                .refresh-btn:hover {{ background-color: #555; }}
            }}
        </style>
    </head>
    <body>
        <div class="header">Receiver Web Server</div>
        <div id="log-container">
            {''.join(f'<div class="log-entry">{log}</div>' for log in logs)}
        </div>
        <div style="text-align: center;">
            <button class="refresh-btn" onclick="location.reload();">Refresh</button>
        </div>
        <div class="footer">&copy; 2024 leelsey</div>
    </body>
    </html>
    """

class RequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Override to suppress default logging in HTTP server
        pass

    def do_GET(self):
        parsed_path = urlparse(self.path)
        client_address = f"{self.client_address[0]}:{self.server.server_port}" if verbose else ""

        if parsed_path.path == "/favicon.ico":
            log_request(parsed_path.path, self.command, log_only_in_cli=True, client_address=client_address)
            self.send_response(404)
            self.end_headers()
        elif parsed_path.path == "/logs":
            self.send_logs()
        else:
            self.handle_home(parsed_path, client_address)

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode('utf-8')
        parsed_path = urlparse(self.path)
        client_address = f"{self.client_address[0]}:{self.server.server_port}" if verbose else ""
        self.handle_home(parsed_path, client_address, body)

    def handle_home(self, parsed_path, client_address, body=None):
        # Process parameters only if path is root (`/`)
        if parsed_path.path == "/":
            query_params = parse_qs(parsed_path.query)
            query_json = {k: (v[0] if len(v) == 1 else v) for k, v in query_params.items()} if query_params else None
            query_value = json.dumps(query_json, separators=(",", ":")) if query_json else ""
        else:
            # If path is not root, treat it as a plain route without parsing query parameters
            query_value = None
            query_json = None

        # Log request based on route and verbose mode
        log_request(parsed_path.path, self.command, query_value=query_value or None, body=body, client_address=client_address)

        # Handle specific parameters if they are present and on the root path
        if query_json and (("q" in query_json or "req" in query_json) and ("p" in query_json or "rep" in query_json)):
            query = query_json.get("q", query_json.get("req", ""))
            target = query_json.get("p", query_json.get("rep", ""))
            if target:
                response_text = send_request_to_target(query, target)
                self.send_response(200)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                self.wfile.write(response_text.encode("utf-8"))
                return

        response = query_value if query_value else ""
        self.send_response(200)
        self.send_header("Content-type", "application/json" if query_value else "text/plain")
        self.end_headers()
        self.wfile.write(response.encode('utf-8') if query_value else b'')

    def send_logs(self):
        html_content = generate_logs_html()
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(html_content.encode('utf-8'))

def run_server(ip, port):
    server = HTTPServer((ip, port), RequestHandler)
    print(f"Server running on {ip}:{port}")
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.start()

    def shutdown_server(signum, frame):
        print("\nShutting down the server gracefully...")
        server.shutdown()
        server_thread.join()
        server.server_close()
        print("Server shutdown completed.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_server)
    server_thread.join()

def main():
    global verbose
    parser = argparse.ArgumentParser(description="Receiver Web Server")
    parser.add_argument("-i", "--ip", default="0.0.0.0", help="IP address to bind")
    parser.add_argument("-p", "--port", type=int, default=80, help="Port number to bind")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("-V", "--version", action="version", version="Receiver Version 0.1.0", help="Show version")
    args = parser.parse_args()

    verbose = args.verbose
    configure_logging(verbose)
    run_server(args.ip, args.port)

if __name__ == "__main__":
    main()
