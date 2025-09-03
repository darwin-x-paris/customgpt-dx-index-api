from flask import Flask
import os
from dotenv import load_dotenv


def create_app() -> Flask:
	load_dotenv()
	app = Flask(__name__)
	app.config['API_KEY'] = os.getenv('API_KEY')

	from .routes import api_bp
	app.register_blueprint(api_bp)

	return app


