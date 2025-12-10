from flask import Flask
from .config import Config

def create_app(config_class=Config):
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.from_object(config_class)

    # Initialize Database
    from . import db
    db.init_app(app)

    # Register Blueprints
    from .blueprints import auth, main, posts, claims, api
    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(posts.bp)
    app.register_blueprint(claims.bp)
    app.register_blueprint(api.bp)

    return app
