# Ecouter — Backend Documentation

How the server side of Ecouter works, from the database up to every route.

---

## Table of Contents

1. [How the App Starts](#1-how-the-app-starts)
2. [The Database Layer](#2-the-database-layer)
3. [Models — What Each Table Stores](#3-models--what-each-table-stores)
4. [How Routes Work](#4-how-routes-work)
5. [Auth Routes](#5-auth-routes)
6. [Dashboard and Discovery](#6-dashboard-and-discovery)
7. [Collections](#7-collections)
8. [Ratings, Notes, and Mood Tags](#8-ratings-notes-and-mood-tags)
9. [Album Detail](#9-album-detail)
10. [Comments and Voting](#10-comments-and-voting)
11. [Search and Artist Pages](#11-search-and-artist-pages)
12. [Helper Functions](#12-helper-functions)
13. [Configuration and Environment](#13-configuration-and-environment)

---

## 1. How the App Starts

`ecouter.py` uses the **application factory pattern**. Instead of creating the Flask app at the top of the file, everything is wrapped inside a function called `create_app()`.

```python
def create_app(config_class=DevelopmentConfig):
    app = Flask(__name__)
    app.config.from_object(config_class)
    ...
    return app
```

This matters because:
- The app is only created when you call `create_app()`, not at import time
- It makes the config swappable (development vs testing vs production)
- Routes defined inside the function have access to `app`, `db`, and the Spotify client via Python closures

**Startup sequence** (everything inside `create_app()`):

1. Load config from `config.py`
2. Call `init_db(app)` — connects SQLAlchemy to the app and creates any missing tables
3. Set up Flask-Login — handles sessions and the `current_user` proxy
4. Initialise the Spotify client — attached to the app as `app.spotify`
5. Run `seed_mood_tags()` — inserts the 15 mood tags if they don't exist yet
6. Define all route functions
7. Return the configured app

---

## 2. The Database Layer

All database access goes through **SQLAlchemy** — a Python ORM that lets you write Python classes instead of SQL.

The `db` object is created once in `models/database.py`:

```python
from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()
```

Every model imports this same `db`. When `init_db(app)` is called, it binds `db` to the specific Flask app:

```python
def init_db(app):
    db.init_app(app)
    with app.app_context():
        db.create_all()  # creates any tables that don't exist yet
```

`db.create_all()` is safe to call every startup — it only creates missing tables, never drops or modifies existing ones.

### The Session

Think of `db.session` as a staging area. You put changes in, then commit them all at once:

```python
db.session.add(new_user)   # stage the new row
db.session.commit()        # write to disk
```

If something goes wrong mid-route, you can roll back:

```python
db.session.rollback()
```

---

## 3. Models — What Each Table Stores

### User (`users` table)

One row per registered account.

| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | Auto-increment |
| username | String(80) | Unique |
| email | String(120) | Unique, used to log in |
| password_hash | String(256) | Never plain text |
| created_at | DateTime | Set on creation |

Passwords are hashed using `pbkdf2:sha256` via Werkzeug. This algorithm is specified explicitly because macOS ships with LibreSSL which does not support `scrypt` (Werkzeug's default in newer versions).

```python
def set_password(self, password):
    self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

def check_password(self, password):
    return check_password_hash(self.password_hash, password)
```

`UserMixin` (from Flask-Login) gives the User class `is_authenticated`, `is_active`, `is_anonymous`, and `get_id()` automatically.

---

### Album (`albums` table)

One row per unique Spotify album, shared across all users. Created the first time any user adds the album to a collection.

| Column | Type | Notes |
|--------|------|-------|
| spotify_id | String(100) | Unique, indexed |
| name | String(255) | Album title |
| artist | String(255) | Artist name(s) |
| artist_id | String(100) | Spotify artist ID for artist page |
| image_url | String(500) | Album cover URL |
| tracklist | Text | JSON string — see below |
| duration_ms | Integer | Total album length |
| total_tracks | Integer | Number of tracks |

**The tracklist column** stores a JSON string because SQLite has no native array type. It is fetched from Spotify lazily — the first time someone visits the album detail page — and then cached in this column. Routes parse it with `json.loads()`.

---

### Collection (`collections` table)

A named group of albums belonging to one user.

| Column | Type | Notes |
|--------|------|-------|
| name | String(255) | Collection name |
| is_public | Boolean | Default False |
| user_id | Integer FK | Owner |
| last_opened_at | DateTime | Stamped when owner views it |

Albums and collections have a **many-to-many** relationship. SQLAlchemy handles this through the `collection_albums` join table — a plain `db.Table` with two foreign key columns (`collection_id`, `album_id`) that form a composite primary key. This prevents the same album appearing twice in the same collection.

---

### UserAlbum (`user_albums` table)

The most important model. Stores one row per user per album, carrying all per-user data for that album.

| Column | Type | Notes |
|--------|------|-------|
| user_id | Integer FK | |
| album_id | Integer FK | |
| rating | Integer | 1=Like, -1=Dislike, None=unrated |
| notes | Text | Private to this user |
| last_viewed_at | DateTime | Stamped on album detail visits |

A `UniqueConstraint` on `(user_id, album_id)` ensures one row per user per album.

`RATING_LIKE = 1` and `RATING_DISLIKE = -1` are exported constants used throughout the routes.

---

### MoodTag and AlbumMood

`MoodTag` is a fixed lookup table of 15 tags across 5 categories, seeded at startup:

| Category | Tags |
|----------|------|
| Energetic | Hype, Upbeat, Motivating |
| Emotional | Melancholic, Heartfelt, Nostalgic |
| Calm | Relaxing, Focused, Dreamy |
| Dark | Brooding, Intense, Haunting |
| Romantic | Sensual, Tender, Euphoric |

`AlbumMood` records one user applying one tag to one album. A `UniqueConstraint` on `(user_id, album_id, mood_tag_id)` prevents duplicates. The 3-tag-per-album limit is enforced in the route, not the model.

---

### Comment and CommentVote

`Comment` supports threading via a **self-referential foreign key**:
- `parent_id = None` → top-level comment
- `parent_id = <id>` → reply to that comment

Replies are accessible via `comment.replies` (a SQLAlchemy relationship).

The `score` property is computed in Python — not stored in the database:

```python
@property
def score(self):
    return sum(v.value for v in self.votes)
```

`CommentVote` stores `value = 1` (upvote) or `-1` (downvote). A `UniqueConstraint` on `(user_id, comment_id)` means one vote per user per comment.

---

## 4. How Routes Work

All routes are defined inside `create_app()`. A route is a Python function decorated with `@app.route(url)`. Flask calls it when a matching request arrives.

```python
@app.route('/album/<int:album_id>')
@login_required
def album_detail(album_id):
    album = Album.query.get_or_404(album_id)
    ...
    return render_template('album_detail.html', album=album, ...)
```

**Common patterns:**

- `Album.query.get_or_404(id)` — fetches a row or returns a 404 page
- `@login_required` — redirects to `/login` if the user isn't authenticated
- `current_user` — Flask-Login proxy for the logged-in user
- `request.form.get('key')` — reads POST form data
- `request.args.get('key')` — reads GET query string data
- `jsonify({...})` — returns a JSON response for AJAX calls
- `flash('message', 'category')` — queues a one-time notification for the next page

---

## 5. Auth Routes

### `GET /` — Landing page
Checks `current_user.is_authenticated`. If already logged in, redirects to dashboard. Otherwise renders `landing.html`.

### `GET/POST /signup`
- **GET**: renders `signup.html` with a blank `SignupForm`
- **POST**: validates the form, checks for duplicate email/username, creates a `User` row, hashes the password with `pbkdf2:sha256`, redirects to `/login`

### `GET/POST /login`
- **GET**: renders `login.html` with a blank `LoginForm`
- **POST**: looks up the user by email, calls `user.check_password()`, calls `login_user(user)` on success

### `GET /logout`
Calls `logout_user()` and redirects to `/login`.

---

## 6. Dashboard and Discovery

`GET /dashboard` is the most complex route. It runs up to 6 separate database queries to power the discovery sections.

### Mood Filter

The dashboard accepts two query parameters:
- `moods` — comma-separated mood tag IDs (e.g. `?moods=1,3,5`)
- `mood_mode` — `any` (default) or `all`

When mood tags are active, the `apply_mood_filter()` helper narrows the pool of album IDs before the discovery queries run.

- **`any` mode**: album must have at least one of the selected tags
- **`all` mode**: album must have every selected tag

### Discovery Sections

All sections query from collections (the `is_public` filter was removed so private collections also contribute):

| Section | How it works |
|---------|-------------|
| **Recent Activity** | `UserAlbum` rows for `current_user` ordered by `last_viewed_at DESC`, limit 6. Also shows collections ordered by `last_opened_at`. |
| **Trending This Week** | `UserAlbum` rows with `rating = 1` and `updated_at >= 7 days ago`, grouped by album, ordered by count. |
| **Top Rated** | Same as Trending but no date filter — all-time like counts. |
| **New Arrivals** | Albums ordered by `Album.id DESC` (most recently added to the database). |
| **You Might Like** | Albums the community has liked that *this user* has not rated yet. Uses a subquery to exclude already-rated albums. |

### Template Variables Passed

```
recently_viewed, recent_collections,
trending, top_rated, new_arrivals, unrated,
collections, ratings, all_mood_tags,
active_mood_ids, mood_mode, no_public_albums
```

`ratings` is a `{album_id: rating}` dict built in one query so the template never hits the database per album.

---

## 7. Collections

### `GET /collections`
Lists all collections for `current_user`, newest first.

### `GET /collection/<id>` — view_collection
Fetches the collection, checks ownership if private. Stamps `last_opened_at` so the dashboard Recent Activity section can track it. Passes `is_owner` to the template so edit/delete controls only show to the owner.

### `POST /create_collection`
Handles two cases:
- Regular POST (from the create collection page) → saves and redirects
- AJAX POST (from the search modal, detected via `X-Requested-With: XMLHttpRequest` header) → saves and returns JSON `{id, name}`

### `POST /add_to_collection`
Called from the search page via AJAX. Looks up the album by `spotify_id` and creates an `Album` row if it doesn't exist yet. Then appends it to `collection.albums` via the SQLAlchemy many-to-many relationship. Returns JSON.

---

## 8. Ratings, Notes, and Mood Tags

### `POST /rate_album`

Upsert logic — always look for an existing row first:

```
existing row found AND same rating → set rating = None (toggle off)
existing row found AND different rating → update rating
no existing row → create UserAlbum with new rating
```

Returns `{status, rating}` JSON. The `status` value (`removed`, `updated`, `added`) tells the JavaScript how to update the button states.

### `POST /save_note`

Creates or updates the `notes` field on the user's `UserAlbum` row. Returns `{status: 'ok'}`.

### `POST /tag_mood`

Toggle logic:
1. Check if this exact tag is already applied → delete it if so (toggle off)
2. Count how many tags this user has on this album → reject if ≥ 3
3. Otherwise create a new `AlbumMood` row

Returns `{status}` which is one of: `added`, `removed`, `limit_reached`.

---

## 9. Album Detail

`GET /album/<id>` is the most data-heavy route. It does the following in order:

1. **Fetch the Album row** — `get_or_404`
2. **Stamp `last_viewed_at`** — finds or creates the `UserAlbum` row and sets `last_viewed_at = datetime.utcnow()`
3. **Lazy-load tracklist** — if `album.tracklist` is empty, calls `app.spotify.album(spotify_id)`, builds the track list, saves it to the database
4. **Parse the tracklist** — `json.loads(album.tracklist)`, adds a formatted `duration` string to each track
5. **Get user's rating and notes** from their `UserAlbum` row
6. **Count community likes/dislikes** — two simple `.count()` queries
7. **Aggregate mood counts** — a GROUP BY query joining `MoodTag` and `AlbumMood`, ordered by count descending
8. **Get user's applied mood IDs** — for highlighting the active tags in the picker
9. **Fetch top-level comments** — `parent_id = None` only; replies are loaded via `comment.replies`
10. **Build user_votes dict** — `{comment_id: value}` for the current user across all visible comments

---

## 10. Comments and Voting

### `POST /comment`
Creates a `Comment` row. If `parent_id` is present in the form data, it's a reply. Redirects back to the album detail page anchored to `#comments`.

### `POST /vote_comment`

Toggle logic for votes:

```
existing vote, same value  → delete it (un-vote)
existing vote, diff value  → switch it (up ↔ down)
no existing vote           → create new CommentVote
```

Returns `{status, score}` JSON so JavaScript can update the score display without reloading.

---

## 11. Search and Artist Pages

### `GET /search`
Accepts a `query` GET parameter. Calls `app.spotify.search(q=query, type='album', limit=12)`. For each result, checks if it already exists in the local `albums` table so the template can show a link to the detail page and the user's existing rating.

Passes `collections` to the template for the Add to Collection modal.

### `GET /artist/<spotify_artist_id>`
Fetches artist info and discography entirely from Spotify — no artist model needed. Attaches local data (`local_id`, `user_rating`) to any albums that exist in the database.

---

## 12. Helper Functions

Defined inside `create_app()` so they are available to all routes via closure.

### `ms_to_duration(ms)`
Converts milliseconds to a readable string like `4:32`. Returns `None` if `ms` is falsy.

### `get_user_ratings(user_id)`
Returns `{album_id: rating}` for all albums a user has rated. Called once per page request — the dict is passed to the template so it never queries the database per album.

### `get_user_mood_ids(user_id, album_id)`
Returns a list of `mood_tag_id` values the user has applied to a specific album. Used on the album detail page to highlight active mood tags.

---

## 13. Configuration and Environment

### config.py

Three classes inherit from a base `Config`:

```python
class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

class DevelopmentConfig(Config):
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///album_platform.db")
    DEBUG = True

class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    DEBUG = False
```

### .env file

Required in the project root — never committed to Git:

```
CLIENT_ID=your_spotify_client_id
CLIENT_SECRET=your_spotify_client_secret
SECRET_KEY=any-long-random-string
```

### forms.py

`SignupForm` and `LoginForm` are Flask-WTF form classes. **Never import from `models` inside `forms.py`** — it creates a circular import that crashes the app. The `Email()` validator requires `pip install email-validator`.

Every HTML form must include `{{ form.hidden_tag() }}` to pass the CSRF token. Without it, Flask-WTF silently rejects every form submission and the form just refreshes with no error message.

### Running the App

```bash
flask --app ecouter run
```

Or create a `.flaskenv` file:

```
FLASK_APP=ecouter
FLASK_DEBUG=1
```

Then just use `flask run`.