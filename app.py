import os

from flask import Flask, jsonify, render_template, request

from shazam_client import ShazamClientError, search_tracks

app = Flask(__name__)


def rapidapi_key():
    return os.getenv("RAPIDAPI_KEY", "").strip()


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/results")
def results():
    query = request.form.get("query", "").strip()

    if not query:
        return render_template(
            "results.html",
            query="",
            tracks=[],
            error="Type a song, artist, or lyric fragment first.",
        ), 400

    api_key = rapidapi_key()
    if not api_key:
        return render_template(
            "results.html",
            query=query,
            tracks=[],
            error="This local copy needs a RAPIDAPI_KEY before it can search Shazam.",
        ), 503

    try:
        tracks = search_tracks(query, api_key=api_key)
    except ShazamClientError as error:
        return render_template(
            "results.html",
            query=query,
            tracks=[],
            error=error.user_message,
        ), error.status_code

    return render_template(
        "results.html",
        query=query,
        tracks=tracks,
        error=None,
    )


@app.get("/health")
def health():
    return jsonify(status="ok", api_key_configured=bool(rapidapi_key()))


if __name__ == "__main__":
    app.run(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
    )
