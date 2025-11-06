from http.server import BaseHTTPRequestHandler, HTTPServer
from service import vulnerability_service as vul_service
from dotenv import load_dotenv
import json
import os
import threading


""""

    Manage the WebHook we use to receive vulnerabilities from other sources like BurpSuite
    Creates a Webhook that listen on /vulnerability for vulnerabilities and create them.

"""

# -    load the .env file   -
load_dotenv()

WEBHOOK_PORT = os.getenv("WEBHOOK_PORT")
WEBHOOK_SERVER = os.getenv("WEBHOOK_SERVER")
server_address = (WEBHOOK_SERVER, int(WEBHOOK_PORT))

class HttpHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        print(self.path)
        if '/vulnerability' in self.path:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body)

                print("Received data", data)

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"status": "received"}')

                if self.path == '/vulnerability/ssl':
                    vul_service.create_ssl_vul(data)
                    
                else:
                    data = json.loads(data)
                    for vulnerability in data:
                        vul_service.create_generic_vul(vulnerability)      

            except json.JSONDecodeError:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"error": "Invalid JSON"}')
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error": "Not Found"}')
    
    def log_message(self, format, *args):
        return  # Suppress logging

server = HTTPServer(server_address, HttpHandler)

def start_webhook():       

    print(f"[+] WebHook Listening on port {WEBHOOK_PORT}")

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

def stop_webhook():
    server.shutdown()