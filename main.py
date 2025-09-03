from app import create_app
import os


app = create_app()


if __name__ == "__main__":
	# Only run the built-in dev server when not in production
	production_env = os.getenv("ENV", "").strip().lower() == "PROD"
	if not production_env:
		app.run(host="0.0.0.0", port=5000, debug=True)


