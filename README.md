# Track Search 🎧

> a tiny Flask side quest for asking Shazam “what track am I thinking of?” without turning it into a whole music app.

I built the first version of this in 2022 as a very small Flask + RapidAPI experiment: submit a song name, call Shazam, loop over the returned hits, and render some cards.

It worked, but it also contained the exact kind of early-project shortcuts that become interesting later: an API credential in source, a template coupled directly to a deeply nested third-party response, no timeout/error states, and a button labelled **Download** even though the app did not own or host any audio.

The current pass keeps the project small while fixing the boundaries that matter.

`Python` · `Flask` · `requests` · `Jinja` · `Shazam via RapidAPI` · `unittest`

## what it does

- search Shazam by song, artist, or another short query
- keep the RapidAPI credential outside source in `RAPIDAPI_KEY`
- time out stalled upstream requests instead of hanging forever
- distinguish rate-limit, authentication, network, malformed-response and empty-result states
- normalize Shazam's nested response into a tiny `Track` model before rendering
- tolerate missing artwork, artist names, actions and links
- deduplicate returned tracks by stable Shazam key
- validate outbound URLs before putting them into the page
- show **Open in Shazam** / **Listen** rather than pretending the app downloads music
- lazy-load third-party artwork with `referrerpolicy="no-referrer"`
- expose a tiny `/health` endpoint for local checks
- test response normalization without touching the real API
- run syntax/tests/credential guards in GitHub Actions

No account. No database. No analytics. No hosted audio.

## request flow

```text
browser form
    │
    ▼
Flask /results
    │
    ├── blank query -> validation state
    ├── missing RAPIDAPI_KEY -> configuration state
    │
    ▼
shazam_client.search_tracks()
    │
    ├── 10 second timeout
    ├── RapidAPI headers
    └── query params
            │
            ▼
      Shazam search API
            │
      ┌─────┼──────────────┐
      │     │              │
     429  401/403       success
      │     │              │
      │     │              ▼
      │     │        parse + normalize
      │     │              │
      └─────┴──────────────┘
            │
            ▼
      small Track objects
            │
            ▼
        Jinja cards
```

The important change is that the template no longer knows Shazam's raw response shape.

## the normalization boundary

The original template reached straight through structures like:

```text
hit -> track -> images -> background
hit -> track -> hub -> actions -> [1] -> uri
hit -> track -> share -> subject
```

That means one missing field or API-shape change can blow up rendering.

The current client converts each hit into:

```python
Track(
    key="...",
    title="...",
    artist="...",
    image_url="..." | None,
    shazam_url="..." | None,
    listen_url="..." | None,
)
```

The web layer only renders that shape.

```text
third-party payload
       │
       ▼
 defensive parsing
       │
       ▼
   Track model
       │
       ▼
     template
```

That is enough architecture for a project this size.

## links are not downloads

The 2022 version labelled one Shazam action URL as **Download**.

The application has no download service, no audio storage and no ownership of those files, so that wording was misleading.

The current UI uses:

```text
Open in Shazam ↗
Listen ↗
```

only when the API returns usable links.

## failure states

A network-backed search has more states than “results or nothing.”

The server currently handles:

```text
blank query
missing local API configuration
connection failure
request timeout
RapidAPI authentication failure
429 rate limit
other upstream HTTP error
invalid JSON
valid response with no tracks
successful results
```

A timeout is capped at 10 seconds so a broken upstream does not leave a request hanging indefinitely.

## credentials

Create the environment variable locally:

```bash
export RAPIDAPI_KEY="your-key-here"
```

PowerShell:

```powershell
$env:RAPIDAPI_KEY="your-key-here"
```

The key is deliberately **not** stored in `.env` or source control.

> The original 2022 repository committed a RapidAPI key directly in `app.py`. It has been removed from the current branch, but Git history is immutable unless explicitly rewritten. Treat the historical key as compromised and rotate/revoke it in RapidAPI.

## run it

Python 3.10+ is required by the current type syntax; CI uses Python 3.12.

```bash
git clone https://github.com/SenithUmesha/shazam-search-tracks.git
cd shazam-search-tracks
python -m venv .venv
```

Activate the environment, then:

```bash
pip install -r requirements.txt
export RAPIDAPI_KEY="your-key-here"
python app.py
```

Open `http://127.0.0.1:5000`.

Health check:

```text
GET /health
```

returns whether the app is running and whether an API key is configured, without exposing the key itself.

## project shape

```text
shazam-search-tracks/
├── app.py
├── shazam_client.py
├── requirements.txt
├── templates/
│   ├── index.html
│   └── results.html
├── static/
│   └── style.css
├── tests/
│   └── test_shazam_client.py
├── docs/
│   └── engineering.md
└── .github/
    └── workflows/
        └── ci.yml
```

`app.py` owns HTTP/browser flow.

`shazam_client.py` owns the external API contract, timeout, status handling, URL filtering and payload normalization.

The templates stay presentation-only.

## tests + CI

Tests use the Python standard library:

```bash
python -m unittest discover -s tests -v
```

They cover:

- query normalization
- outbound URL validation
- malformed hit handling
- fallback artist/title behavior
- nested response normalization
- result deduplication
- unsafe action rejection

GitHub Actions also compiles the Python source and checks that a literal RapidAPI credential is not accidentally reintroduced.

The unit tests do **not** call Shazam. That keeps CI deterministic and avoids burning API quota just to prove parsing logic works.

## visual pass

The Bootstrap/jQuery/Popper stack was unnecessary for two server-rendered pages, so the current UI is plain HTML + CSS:

- compact dark music-search shell
- responsive 3 → 2 → 1 result grid
- semantic search form
- proper error/empty states
- lazy artwork
- clear external-link actions
- no JavaScript runtime dependency

## boundaries

This is a search experiment, not a streaming/downloading product.

It intentionally does not include:

- accounts or saved libraries
- Spotify/Apple Music authentication
- audio hosting
- downloads
- background jobs
- a database
- client-side state management
- recommendation logic

It also still depends on a third-party RapidAPI/Shazam contract. Provider availability, pricing, response fields and rate limits are outside this repository's control.

## if i kept going

The next useful improvements would be a provider adapter test with recorded/sanitized fixture payloads, optional query pagination, and a small cache to reduce repeated identical searches.

I would not add a database or frontend framework unless the product actually grew state that needed them.

More detail: [`docs/engineering.md`](docs/engineering.md)
