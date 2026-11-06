from flask import Flask, render_template

app = Flask(__name__)


@app.get("/settings/account")
def account_settings():
    return render_template("account_settings.html", email="ada@example.com")
