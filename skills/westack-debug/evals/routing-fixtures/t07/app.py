from flask import Flask, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-only"
app.config["SESSION_COOKIE_SECURE"] = True

FAKE_USERS = {"ada@example.com": "example-only"}


def check(email, password):
    return FAKE_USERS.get(email) == password


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if check(request.form["email"], request.form["password"]):
            session["user"] = request.form["email"]
            return redirect(url_for("home"))
    return render_template("login.html")


@app.get("/")
def home():
    if "user" not in session:
        return redirect(url_for("login"))
    return "Hello, " + session["user"]
