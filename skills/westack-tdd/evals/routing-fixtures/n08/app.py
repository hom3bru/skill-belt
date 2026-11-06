from flask import Flask

app = Flask(__name__)

NOTES = [{"id": 1, "title": "First", "body": "hello"}]


@app.get("/notes")
def notes():
    return {"notes": NOTES}
