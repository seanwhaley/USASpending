from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
import webbrowser
from pathlib import Path
import sys

class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Change to the project root directory
        project_root = Path(__file__).parent.parent
        os.chdir(project_root)
        super().__init__(*args, **kwargs)

    def translate_path(self, path):
        # Redirect root to the dashboard HTML
        if path == '/':
            return str(Path('docs/templates/test_coverage_dashboard.html'))
        return super().translate_path(path)

def run_server(port=8000):
    server_address = ('', port)
    httpd = HTTPServer(server_address, DashboardHandler)
    print(f"Starting server on http://localhost:{port}")
    
    # Open the browser
    webbrowser.open(f'http://localhost:{port}')
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()

if __name__ == '__main__':
    # Allow port to be specified as command line argument
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    run_server(port)