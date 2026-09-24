from app import create_app
from pyngrok import ngrok
import os
import certifi

# Create Flask app
app = create_app("development")

# Ensure Python uses proper SSL certificates
os.environ["SSL_CERT_FILE"] = certifi.where()


if __name__ == "__main__":
    port = 9123  # Flask port

    # Start ngrok tunnel
    public_url = ngrok.connect(port)
    print(f" * ngrok tunnel available at: {public_url}")

    # Optional: display a message for users
    print(f" * Visit {public_url} to access your app from the web")

    # Start Flask
    # Disable debug reloader, otherwise ngrok might open a second tunnel (common error)
    app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False)


