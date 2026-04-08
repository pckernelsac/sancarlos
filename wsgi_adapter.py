"""
Adaptador ASGI → WSGI ligero para Phusion Passenger.

Ejecuta la app ASGI (FastAPI) dentro de un event loop síncrono
por cada request WSGI. Compatible con Passenger en cPanel.
"""
import asyncio
import io
import sys


def asgi_to_wsgi(asgi_app):
    """Convierte una app ASGI en una callable WSGI."""

    def wsgi_app(environ, start_response):
        # Construir el scope ASGI desde environ WSGI
        path = environ.get("PATH_INFO", "/")
        query = environ.get("QUERY_STRING", "")
        server_name = environ.get("SERVER_NAME", "localhost")
        server_port = environ.get("SERVER_PORT", "80")
        scheme = environ.get("wsgi.url_scheme", "http")

        headers = []
        for key, value in environ.items():
            if key.startswith("HTTP_"):
                header_name = key[5:].lower().replace("_", "-")
                headers.append((header_name.encode(), value.encode()))
            elif key == "CONTENT_TYPE" and value:
                headers.append((b"content-type", value.encode()))
            elif key == "CONTENT_LENGTH" and value:
                headers.append((b"content-length", value.encode()))

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": environ.get("REQUEST_METHOD", "GET"),
            "path": path,
            "root_path": environ.get("SCRIPT_NAME", ""),
            "query_string": query.encode("latin-1"),
            "scheme": scheme,
            "server": (server_name, int(server_port)),
            "headers": headers,
        }

        # Leer el body del request WSGI
        try:
            content_length = int(environ.get("CONTENT_LENGTH") or 0)
        except (ValueError, TypeError):
            content_length = 0

        if content_length > 0:
            body = environ["wsgi.input"].read(content_length)
        else:
            body = b""

        # Estado compartido entre las coroutines
        response_started = False
        status_code = None
        response_headers = None
        body_parts = []

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message):
            nonlocal response_started, status_code, response_headers

            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                response_headers = [
                    (k.decode() if isinstance(k, bytes) else k,
                     v.decode() if isinstance(v, bytes) else v)
                    for k, v in message.get("headers", [])
                ]
            elif message["type"] == "http.response.body":
                chunk = message.get("body", b"")
                if chunk:
                    body_parts.append(chunk)

        # Ejecutar la app ASGI en un event loop síncrono
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(asgi_app(scope, receive, send))
        finally:
            loop.close()

        # Responder al WSGI
        status_line = f"{status_code} OK" if status_code else "500 Internal Server Error"
        # Mapear status code a frase estándar
        phrases = {
            200: "OK", 201: "Created", 204: "No Content",
            301: "Moved Permanently", 302: "Found", 303: "See Other",
            304: "Not Modified", 307: "Temporary Redirect",
            400: "Bad Request", 401: "Unauthorized", 403: "Forbidden",
            404: "Not Found", 405: "Method Not Allowed",
            422: "Unprocessable Entity", 423: "Locked",
            500: "Internal Server Error", 502: "Bad Gateway",
            503: "Service Unavailable",
        }
        if status_code:
            phrase = phrases.get(status_code, "OK")
            status_line = f"{status_code} {phrase}"

        start_response(status_line, response_headers or [])
        return body_parts

    return wsgi_app
