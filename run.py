"""Arranque en desarrollo:  python run.py   →  http://127.0.0.1:5000

En producción usar un servidor WSGI, p. ej.:
    waitress-serve --port=8000 --call ciclonai:create_app      (Windows)
    gunicorn "ciclonai:create_app()"                            (Linux)
"""
import os

from ciclonai import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "1") == "1")
