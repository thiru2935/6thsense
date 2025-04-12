from flask import Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'  # Change this to a secure value
app.config['TEMPLATES_AUTO_RELOAD'] = True

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)