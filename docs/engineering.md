# Engineering notes — Track Search

This repository is intentionally small. The interesting part is the boundary between a Flask app and a third-party music-search API.

The 2022 version put most assumptions directly in one route and one Jinja template. The current version keeps the same product while making those assumptions explicit and testable.

## 1. System shape

```text
browser
  │
  ▼
Flask app.py
  │
  ├── request validation
  ├── environment configuration
  ├── HTTP status / page selection
  │
  ▼
shazam_client.py
  │
  ├── timeout policy
  ├── RapidAPI request
  ├── upstream error mapping
  ├── payload parsing
  ├── URL validation
  └── Track normalization
  │
  ▼
Shazam search via RapidAPI
```

The templates receive normalized `Track` objects rather than raw API dictionaries.

## 2. Why the API boundary matters

The original route effectively did:

```text
read form field
  -> call API
  -> response.json()
  -> data["tracks"]["hits"]
  -> pass raw hits to Jinja
```

This makes every layer depend on the provider's exact response shape.

The current boundary instead does:

```text
external JSON
    │
    ▼
parse_tracks()
    │
    ▼
Track
    │
    ▼
template
```

A provider-shape change should ideally require changes in one module, not throughout the UI.

## 3. Configuration

The application reads the RapidAPI credential at request time from:

```text
RAPIDAPI_KEY
```

Optional runtime configuration:

```text
HOST
PORT
FLASK_DEBUG
```

No secret value is committed into current source.

The application deliberately does not ship a `.env` parser dependency. Deployment environments, shells, container runtimes, or process managers can inject environment variables directly.

## 4. Historical credential issue

The first public commit included a literal RapidAPI credential in `app.py`.

Removing that value from current `main` prevents new clones from seeing it in the working tree, but does not remove it from old commits.

Security response should therefore be:

```text
remove secret from current source
        +
rotate/revoke provider credential
        +
optionally rewrite Git history if there is a reason to
```

History rewriting alone is not a substitute for rotation once a credential has been public.

## 5. Search query handling

The browser sends a POST form to `/results`.

`app.py` trims the value before doing any provider work.

```text
blank -> validation response
non-blank -> API configuration check -> client
```

The HTML field is also `required` and limited to 120 characters, but server-side validation remains the authoritative boundary because browser validation can be bypassed.

## 6. Request policy

`search_tracks()` sends:

```text
GET https://shazam.p.rapidapi.com/search
```

with the historical request parameters used by the original project:

```text
term=<query>
locale=en-US
offset=0
limit=20
```

and the RapidAPI host/key headers.

The request has a 10-second timeout.

No retry loop is implemented. Automatic retries can amplify rate limiting and would need an explicit backoff policy rather than a blind loop.

## 7. Failure mapping

Provider/runtime failures become `ShazamClientError` instances with a user-facing message and HTTP status.

Current mapping:

```text
requests.Timeout        -> 504
requests.RequestException -> 502
429                     -> 429
401 / 403               -> 503 configuration/provider-auth state
other HTTP error        -> 502
invalid JSON            -> 502
```

The route does not expose Python exception details to the page.

## 8. Payload normalization

The provider result is normalized into:

```python
@dataclass(frozen=True)
class Track:
    key: str
    title: str
    artist: str
    image_url: str | None
    shazam_url: str | None
    listen_url: str | None
```

This is deliberately smaller than Shazam's complete payload.

The product needs enough data to answer:

```text
what is the track?
who is it by?
what does the artwork look like?
where can I open/listen to it?
```

Everything else is discarded at the boundary.

## 9. Missing data

Third-party records are treated as incomplete input, not trusted internal models.

Fallbacks include:

```text
missing title  -> "Untitled track"
missing artist -> "Unknown artist"
missing image  -> CSS music-note placeholder
missing URL    -> omit that action
```

A malformed hit with no usable `track` object is skipped.

## 10. Deduplication

Shazam's `track.key` is used as the preferred logical identity.

```text
first occurrence of key -> keep
later duplicate key     -> skip
```

When a key is missing, normalization falls back to a title/artist identity so the UI can still render an incomplete record.

The fallback is for UI stability, not a guarantee of globally unique track identity.

## 11. URL validation

Provider-supplied strings should not become clickable URLs without a protocol check.

`safe_external_url()` currently accepts only absolute:

```text
http://
https://
```

URLs with a network location.

It rejects values such as:

```text
javascript:...
relative/path
empty strings
```

The current version does not restrict links to a hardcoded allowlist because Shazam action URLs may legitimately point to music-provider hosts. Protocol validation is therefore the chosen boundary.

## 12. Listen action selection

The original template assumed:

```text
hub.actions[1].uri
```

and labelled it "Download".

That is brittle for two reasons:

1. action ordering is an external contract
2. a URI does not mean the app owns downloadable audio

The current parser walks available action objects and takes the first safe absolute URL.

The UI calls it **Listen**.

If the response provides no usable action, no listen button is rendered.

## 13. Template safety

Jinja autoescaping keeps text fields escaped in HTML templates.

The application also normalizes external links before the template receives them.

These are two different boundaries:

```text
text escaping -> prevents API text becoming markup
URL validation -> prevents unsupported URL schemes becoming actions
```

External links use:

```html
target="_blank"
rel="noopener noreferrer"
```

## 14. Artwork privacy and performance

Remote images are loaded only for result cards.

They use:

```html
loading="lazy"
referrerpolicy="no-referrer"
```

Lazy loading avoids eagerly downloading artwork outside the initial viewport.

`no-referrer` prevents the browser from sending the Track Search page URL as the HTTP referrer to the remote image host.

The image host still receives the image request itself; this is not an offline/privacy-isolated app.

## 15. Server-rendered UI

There is no browser application state beyond the submitted form.

That means the project does not need React/Vue/Svelte or a client-side router.

The browser interaction is:

```text
GET /
  -> HTML search form
POST /results
  -> server calls provider
  -> HTML result page
```

The absence of client JavaScript is a feature of the current scale, not a missing technology checkbox.

## 16. Health endpoint

`GET /health` returns:

```json
{
  "status": "ok",
  "api_key_configured": true
}
```

It deliberately reports configuration presence only.

It never returns the actual key and does not call the third-party service, so the health endpoint remains cheap and quota-free.

## 17. Test boundary

Unit tests focus on deterministic code around the external contract:

```text
normalize query
validate URL
normalize hit
handle missing fields
parse collection
deduplicate results
reject unsafe action URLs
```

They do not call RapidAPI.

A live API test would be slower, quota-dependent, credential-dependent and less deterministic. If contract testing became important, a sanitized captured fixture is a better next step.

## 18. CI

GitHub Actions uses Python 3.12 and runs:

```text
pip install -r requirements.txt
python -m compileall -q app.py shazam_client.py tests
python -m unittest discover -s tests -v
credential source guard
```

The credential guard is intentionally repository-specific because the most important historical failure was committing an API key.

It is not a replacement for a general secret scanner, but it makes that exact regression harder to repeat.

## 19. Dependency policy

`requirements.txt` uses compatible ranges rather than freezing the app forever to a 2022 environment:

```text
Flask >=3,<4
requests >=2.31,<3
```

For a deployed production service, a lock file / reproducible build process would be useful. For this small historical side project, the current ranges plus CI are enough to document the runtime without maintaining a large dependency-management setup.

## 20. Current limits

The app intentionally does not implement:

```text
search pagination
query caching
login
saved favorites
streaming
track downloads
OAuth provider integrations
background jobs
persistent storage
```

It also relies on a third-party API product whose contract and subscription requirements can change independently of this repository.

## 21. What I would do for a real product

A production music-discovery service would likely add:

```text
provider abstraction
server-side response cache
structured logging/metrics
rate-limit backoff
provider-specific contract fixtures
request correlation IDs
secret manager integration
multiple music providers / fallbacks
```

If users had accounts or saved libraries, then a database and authentication layer would become justified.

For this repo, the useful engineering lesson is smaller:

> **an external API should end at a deliberate adapter boundary, not leak its entire response shape into the rest of the app.**
