"""CiclonAI — software para procesamiento de minerales (versión Flask)."""
from flask import Flask


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.jinja_env.globals["zip"] = zip
    if config:
        app.config.update(config)

    from .routes import bp
    app.register_blueprint(bp)
    return app
