from flask import Flask, redirect, request, session

from .auth import check_password

app = Flask(__name__)
app.secret_key = "dev-only"


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST" and check_password(request.form["user"], request.form["password"]):
        session["admin"] = request.form["user"]
        return redirect("/")
    return "login form"


@app.get("/")
def home():
    if "admin" not in session:
        return redirect("/login")
    return "admin home"
