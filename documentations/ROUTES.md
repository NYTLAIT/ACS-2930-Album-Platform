# AlbumRank — Backend Routes Reference

Every route in `ecouter.py`, explained in full detail.

---

## Table of Contents

1. [How the App is Structured](#1-how-the-app-is-structured)
2. [Helper Functions](#2-helper-functions)
3. [Auth Routes](#3-auth-routes)
   - [GET `/`](#get-)
   - [GET/POST `/signup`](#getpost-signup)
   - [GET/POST `/login`](#getpost-login)
   - [GET `/logout`](#get-logout)
4. [Dashboard](#4-dashboard)
   - [GET `/dashboard`](#get-dashboard)
5. [Collections](#5-collections)
   - [GET `/collections`](#get-collections)
   - [GET `/collection/<id>`](#get-collectionid)
   - [GET/POST `/create_collection`](#getpost-create_collection)
   - [POST `/edit_collection/<id>`](#post-edit_collectionid)
   - [POST `/delete_collection/<id>`](#post-delete_collectionid)
6. [Album Management](#6-album-management)
   - [POST `/add_to_collection`](#post-add_to_collection)
7. [Ratings and Notes](#7-ratings-and-notes)
   - [POST `/rate_album`](#post-rate_album)
   - [POST `/save_note`](#post-save_note)
8. [Mood Tags](#8-mood-tags)
   - [POST `/tag_mood`](#post-tag_mood)
9. [Album Detail](#9-album-detail)
   - [GET `/album/<id>`](#get-albumid)
10. [Comments](#10-comments)
    - [POST `/comment`](#post-comment)
    - [POST `/vote_comment`](#post-vote_comment)
11. [Search and Discovery](#11-search-and-discovery)
    - [GET `/search`](#get-search)
    - [GET `/artist/<spotify_artist_id>`](#get-artistspotify_artist_id)

---

## 1. How the App is Structured

All routes live inside a function called `create_app()`. This is the **application factory pattern** — the app is only created when you call the function, not when Python imports the file.

```python
def create_app(config_class=DevelopmentConfig):
    app = Flask(__name__)
    app.config.from_object(config_class)
    # ... setup ...
    # ... all routes defined here ...
    return app
```

This matters for two reasons:

1. **Config is swappable** — you can pass `DevelopmentConfig`, `ProductionConfig`, or `TestingConfig` and the app behaves differently without changing any code.
2. **Closures** — routes defined inside `create_app()` automatically have access to `app`, `db`, and `app.spotify` via Python's closure rules. They can "see" variables from the outer function.

**What happens inside `create_app()` before routes are registered:**

| Step | What it does |
|------|-------------|
| `init_db(app)` | Connects SQLAlchemy to the app. Calls `db.create_all()` to create any missing tables. |
| `LoginManager(app)` | Sets up Flask-Login. Registers `login_view = "login"` so `@login_required` knows where to redirect. |
| `app.spotify = ...` | Initialises the Spotify API client using credentials from `.env`. Attaches it to the app so every route can use `app.spotify`. |
| `seed_mood_tags()` | Inserts the 15 mood tags into the database if they don't exist yet. Safe to run on every startup. |

---

## 2. Helper Functions

These are small utility functions defined inside `create_app()`. They are not routes — they are called by routes.

---

### `ms_to_duration(ms)`

Converts a millisecond integer into a human-readable duration string.

```python
ms_to_duration(272000)  # → "4:32"
ms_to_duration(0)       # → None
ms_to_duration(None)    # → None
```

Used when rendering tracklists on the album detail page and when displaying total album duration.

---

### `get_user_ratings(user_id)`

Returns a dictionary of `{album_id: rating}` for every album a user has rated.

```python
ratings = get_user_ratings(current_user.id)
# → {3: 1, 7: -1, 12: 1, ...}
```

**Why this exists:** On pages that show multiple albums (dashboard, collection view), you need to know the user's rating for each album to highlight the Like/Dislike buttons correctly. The naive approach would query the database once per album — very slow. This function does **one query** and returns a dictionary that the template can look up instantly with `ratings.get(album.id)`.

---

### `get_user_mood_ids(user_id, album_id)`

Returns a list of `mood_tag_id` values that a specific user has applied to a specific album.

```python
get_user_mood_ids(current_user.id, album.id)
# → [2, 7]  (the IDs of the mood tags this user has applied)
```

Used on the album detail page to pre-highlight the mood tags the user has already selected.

---

## 3. Auth Routes

---

### `GET /`

**Function:** `index()`  
**Login required:** No

The public landing page.

**Logic:**
1. Check `current_user.is_authenticated`
2. If already logged in → redirect to `/dashboard`
3. Otherwise → render `landing.html`

No data is fetched from the database. The template is purely static marketing content.

---

### `GET/POST /signup`

**Function:** `signup()`  
**Login required:** No

Shows the signup form and handles new account creation.

**GET request:**
- If already logged in → redirect to `/dashboard`
- Otherwise → render `signup.html` with a blank `SignupForm`

**POST request (form submitted):**

```
1. form.validate_on_submit() runs Flask-WTF validation
   - Checks all fields are filled in
   - Checks email format is valid
   - Checks password matches confirm_password
   - Checks CSRF token is present
   If validation fails → re-render signup.html with error messages

2. Check if email already exists in the database
   → flash "An account with that email already exists." and re-render

3. Check if username already exists in the database
   → flash "That username is already taken." and re-render

4. Create a new User object
   user = User(email=..., username=...)
   user.set_password(form.password.data)
   → set_password hashes the password using pbkdf2:sha256

5. Save to database
   db.session.add(user)
   db.session.commit()

6. Log the user in immediately
   login_user(user)

7. Redirect to /dashboard
```

**Why pbkdf2:sha256?** Werkzeug's default hashing algorithm in newer versions is `scrypt`, which requires OpenSSL. macOS ships with LibreSSL which does not support `scrypt`. Specifying `pbkdf2:sha256` ensures the app works on all machines.

**Form fields validated:**
- `email` — must be a valid email format (requires `email-validator` package)
- `username` — 3 to 25 characters
- `password` — minimum 6 characters
- `confirm_password` — must match `password`

---

### `GET/POST /login`

**Function:** `login()`  
**Login required:** No

Shows the login form and authenticates the user.

**GET request:**
- If already logged in → redirect to `/dashboard`
- Otherwise → render `login.html` with a blank `LoginForm`

**POST request (form submitted):**

```
1. form.validate_on_submit() runs Flask-WTF validation
   If validation fails → re-render login.html with error messages

2. Look up user by email
   user = User.query.filter_by(email=form.email.data).first()

3. Check the password
   user.check_password(form.password.data)
   → check_password_hash compares the attempt against the stored hash
   → never decrypts — just checks if they match

4. If user found AND password correct:
   login_user(user)  ← Flask-Login sets the session cookie
   redirect to /dashboard

5. If anything fails:
   flash "Incorrect email or password."
   re-render login.html
```

**Important:** The error message is intentionally vague ("Incorrect email or password" rather than "Email not found" or "Wrong password"). This prevents attackers from finding out which emails are registered.

---

### `GET /logout`

**Function:** `logout()`  
**Login required:** Yes (`@login_required`)

Logs the current user out.

```
1. logout_user()  ← Flask-Login clears the session cookie
2. flash "You have been logged out."
3. redirect to /login
```

Simple and direct — no database writes needed.

---

## 4. Dashboard

---

### `GET /dashboard`

**Function:** `dashboard()`  
**Login required:** Yes  
**Query parameters:** `moods`, `mood_mode`

The main page after login. Powers the entire discovery system. This is the most complex route in the app — it runs multiple database queries to build 5 discovery sections.

---

#### Step 1 — Parse the mood filter

```python
mood_param      = request.args.get("moods", "").strip()
mood_mode       = request.args.get("mood_mode", "any")
active_mood_ids = []
```

The URL can look like `/dashboard?moods=1,3,5&mood_mode=all`. This reads those parameters and converts them to a list of integers.

If the URL has no mood parameters, `active_mood_ids` is an empty list and no filtering is applied.

---

#### Step 2 — Get all album IDs in collections

```python
public_id_rows = (
    db.session.query(collection_albums.c.album_id)
    .join(Collection, Collection.id == collection_albums.c.collection_id)
    .filter(Collection.is_public.is_(True))
    .distinct()
    .all()
)
public_album_ids = [row[0] for row in public_id_rows]
```

This queries the `collection_albums` join table to get every unique album ID that appears in any collection. The `is_public` filter can be removed if you want private collections to also contribute to discovery.

This pool of IDs is what all discovery sections draw from.

---

#### Step 3 — Apply mood filter (if active)

The inner function `apply_mood_filter(base_ids)` takes the pool of album IDs and narrows it down based on the selected mood tags.

**`mood_mode = "any"`** (default):  
Returns albums that have *at least one* of the selected tags applied by any user.

**`mood_mode = "all"`**:  
Returns only albums that have *every* selected tag applied. Uses a `HAVING COUNT(DISTINCT mood_tag_id) = len(active_mood_ids)` clause to enforce this.

If no moods are selected, the function returns the base IDs unchanged.

---

#### Step 4 — Recent Activity

```python
recent_view_rows = (
    UserAlbum.query
    .filter(
        UserAlbum.user_id == current_user.id,
        UserAlbum.last_viewed_at.isnot(None),
    )
    .order_by(UserAlbum.last_viewed_at.desc())
    .limit(6)
    .all()
)
recently_viewed = [row.album for row in recent_view_rows]
```

Fetches the 6 albums this user most recently visited, using the `last_viewed_at` timestamp that gets stamped every time a user lands on an album detail page.

Also fetches the user's 4 most recently opened collections (by `last_opened_at`). If no collections have been opened yet, falls back to the 4 most recently created.

---

#### Step 5 — Trending This Week

```python
one_week_ago = datetime.utcnow() - timedelta(days=7)
trending_rows = (
    db.session.query(Album, func.count(UserAlbum.id).label("like_count"))
    .join(UserAlbum, UserAlbum.album_id == Album.id)
    .filter(
        Album.id.in_(filtered_ids),
        UserAlbum.rating == RATING_LIKE,
        UserAlbum.updated_at >= one_week_ago,
    )
    .group_by(Album.id)
    .order_by(func.count(UserAlbum.id).desc())
    .limit(12)
    .all()
)
trending = [{"album": r[0], "like_count": r[1]} for r in trending_rows]
```

Joins `albums` with `user_albums`, filters to only `rating = 1` (likes) from the past 7 days, groups by album, counts the likes, and orders by that count descending. Returns at most 12 albums with their like counts.

---

#### Step 6 — Top Rated Overall

Same query as Trending but without the `updated_at >= one_week_ago` filter. Returns the all-time most-liked albums.

---

#### Step 7 — New Arrivals

```python
new_arrivals = (
    Album.query
    .filter(Album.id.in_(filtered_ids))
    .order_by(Album.id.desc())
    .limit(12)
    .all()
)
```

Fetches albums ordered by `Album.id DESC` — the highest IDs were added most recently. Simple and fast.

---

#### Step 8 — You Might Like (Unrated by You)

```python
rated_by_me = (
    db.session.query(UserAlbum.album_id)
    .filter(
        UserAlbum.user_id == current_user.id,
        UserAlbum.rating.isnot(None),
    )
    .subquery()
)
unrated_rows = (
    db.session.query(Album, func.count(UserAlbum.id).label("like_count"))
    .join(UserAlbum, UserAlbum.album_id == Album.id)
    .filter(
        Album.id.in_(filtered_ids),
        UserAlbum.rating == RATING_LIKE,
        Album.id.notin_(rated_by_me),
    )
    ...
)
```

First builds a subquery of every album the current user has already rated. Then finds liked albums that are *not in* that subquery. This produces a recommendation list of popular albums the user hasn't touched yet.

---

#### Step 9 — What gets passed to the template

| Variable | Type | Used for |
|----------|------|----------|
| `recently_viewed` | list of Album | Recent Activity section |
| `recent_collections` | list of Collection | Recent Activity section |
| `trending` | list of `{album, like_count}` | Trending section |
| `top_rated` | list of `{album, like_count}` | Top Rated section |
| `new_arrivals` | list of Album | New Arrivals section |
| `unrated` | list of `{album, like_count}` | You Might Like section |
| `collections` | list of Collection | Your Collections chips |
| `ratings` | dict `{album_id: rating}` | Like/Dislike button states across all cards |
| `all_mood_tags` | list of MoodTag | Mood filter bar |
| `active_mood_ids` | list of int | Highlighting active tags |
| `mood_mode` | string `"any"` or `"all"` | Mode toggle display |
| `no_public_albums` | bool | Shows empty state message if True |

---

## 5. Collections

---

### `GET /collections`

**Function:** `collections()`  
**Login required:** Yes

Fetches all collections belonging to the current user, ordered newest first. Renders `collections.html`.

Nothing complex — one query, one template.

---

### `GET /collection/<id>`

**Function:** `view_collection(collection_id)`  
**Login required:** Yes

Shows all albums inside a single collection.

```
1. Fetch the collection by ID (404 if not found)

2. Privacy check:
   If collection.is_public is False AND collection.user_id != current_user.id
   → flash "That collection is private."
   → redirect to /collections

3. Stamp last_opened_at (only for the owner):
   collection.last_opened_at = datetime.utcnow()
   db.session.commit()
   → used by the dashboard Recent Activity section

4. Get the user's ratings dict (one query for all albums)

5. Render view_collection.html with:
   - collection object (which includes collection.albums via SQLAlchemy relationship)
   - ratings dict
   - is_owner boolean (controls whether edit/delete buttons are shown)
```

---

### `GET/POST /create_collection`

**Function:** `create_collection()`  
**Login required:** Yes

Creates a new collection. Handles two different callers:

**Regular POST (from the create collection page):**
```
1. Read name, description, is_public from form
2. Validate name is not empty
3. Create Collection row, save to database
4. flash "Collection created."
5. redirect to /collections
```

**AJAX POST (from the Add to Collection modal on the search page):**

The search page modal has an inline "Create new collection" form. When submitted, JavaScript adds the header `X-Requested-With: XMLHttpRequest`. The route detects this and returns JSON instead of redirecting:

```python
if request.headers.get("X-Requested-With") == "XMLHttpRequest":
    return jsonify({"id": new_col.id, "name": new_col.name})
```

JavaScript receives the new collection's `id` and immediately calls `add_to_collection` with it, so the album gets added to the brand-new collection in one smooth flow.

---

### `POST /edit_collection/<id>`

**Function:** `edit_collection(collection_id)`  
**Login required:** Yes

Updates a collection's name, description, and public/private status.

```
1. Fetch collection (404 if not found)
2. Ownership check: if collection.user_id != current_user.id → deny
3. Update fields from form data
4. db.session.commit()
5. flash "Collection updated."
6. redirect back to the collection's view page
```

If `name` is empty in the form, the existing name is kept unchanged (we only overwrite if a new value was provided).

---

### `POST /delete_collection/<id>`

**Function:** `delete_collection(collection_id)`  
**Login required:** Yes

Deletes a collection permanently.

```
1. Fetch collection (404 if not found)
2. Ownership check: if collection.user_id != current_user.id → deny
3. db.session.delete(collection)
4. db.session.commit()
   → cascade delete removes all entries in collection_albums for this collection
5. flash "Collection deleted."
6. redirect to /collections
```

The albums themselves are **not** deleted — only the collection and its membership entries. Other users' collections that contain the same albums are unaffected.

---

## 6. Album Management

---

### `POST /add_to_collection`

**Function:** `add_to_collection()`  
**Login required:** Yes  
**Called via:** AJAX only — always returns JSON

Adds an album to one of the user's collections. This is the route that bridges Spotify search results (which are not yet in the database) with the local database.

```
1. Read from form data:
   - spotify_id, name, artist, artist_id, release_date, image_url
   - collection_id

2. Validate that spotify_id and collection_id are present

3. Fetch the collection (404 if not found)
   Ownership check: collection.user_id must equal current_user.id

4. Look up the album by spotify_id:
   album = Album.query.filter_by(spotify_id=spotify_id).first()

   If not found → create a new Album row with the data from the form
   db.session.add(album)
   db.session.flush()  ← gets album.id without committing yet

   Note: tracklist and duration are NOT fetched here — that happens lazily
   on the first visit to the album detail page. This keeps search fast.

5. Check if album is already in the collection:
   if album in collection.albums
   → return {"status": "exists", "message": "Already in ..."}

6. Add to collection:
   collection.albums.append(album)
   collection.last_opened_at = datetime.utcnow()
   db.session.commit()

7. Return {"status": "added", "message": "Added to ...", "album_id": album.id}
```

**Why `db.session.flush()` instead of `db.session.commit()`?**  
`flush()` sends the INSERT to the database engine and gets back the auto-generated `id`, but does not permanently commit. If something goes wrong later in the same request (like the collection check failing), the whole operation can be rolled back cleanly. `commit()` at the end makes everything permanent at once.

---

## 7. Ratings and Notes

---

### `POST /rate_album`

**Function:** `rate_album()`  
**Login required:** Yes  
**Called via:** AJAX only — always returns JSON

Likes or dislikes an album. Implements toggle behaviour.

**Input (form data):**
- `album_id` — integer ID of the album in the local database
- `rating` — must be `"1"` (like) or `"-1"` (dislike)

**Logic:**

```
1. Validate inputs — album_id must exist, rating must be "1" or "-1"

2. Fetch the Album row (404 if not found)

3. Look for an existing UserAlbum row:
   user_album = UserAlbum.query.filter_by(
       user_id=current_user.id, album_id=album_id
   ).first()

4. Three cases:

   CASE A — existing row, same rating:
   → user clicked the same button again (toggle off)
   → set user_album.rating = None
   → return {"status": "removed", "rating": None}

   CASE B — existing row, different rating:
   → user switched from Like to Dislike or vice versa
   → set user_album.rating = new_rating
   → return {"status": "updated", "rating": new_rating}

   CASE C — no existing row:
   → first time this user is rating this album
   → create new UserAlbum(user_id=..., album_id=..., rating=...)
   → return {"status": "added", "rating": new_rating}
```

The JavaScript uses the `status` value to decide how to update the buttons — `"removed"` clears the active state, `"updated"` switches which button is highlighted, `"added"` activates the correct button.

---

### `POST /save_note`

**Function:** `save_note()`  
**Login required:** Yes  
**Called via:** AJAX only — always returns JSON

Saves a private note on an album. Notes are only visible to the user who wrote them.

```
1. Read album_id and notes from form data

2. Look for existing UserAlbum row for this user + album

3. If row exists → update notes field
   If row doesn't exist → create a new UserAlbum with notes set

4. Empty note (empty string) is stored as None (NULL in database)

5. Return {"status": "ok"}
```

The JavaScript intercepts the form's `submit` event with `e.preventDefault()` and sends the note via `fetch()` instead, so the page doesn't reload.

---

## 8. Mood Tags

---

### `POST /tag_mood`

**Function:** `tag_mood()`  
**Login required:** Yes  
**Called via:** AJAX only — always returns JSON

Applies or removes a mood tag on an album for the current user.

**Input:**
- `album_id` — local album ID
- `mood_tag_id` — ID of the mood tag to toggle

**Logic:**

```
1. Validate inputs

2. Check if this exact tag is already applied:
   existing = AlbumMood.query.filter_by(
       user_id=current_user.id,
       album_id=album_id,
       mood_tag_id=mood_tag_id
   ).first()

   If found → delete it (toggle off)
   → return {"status": "removed"}

3. Count how many tags this user has on this album:
   current_count = AlbumMood.query.filter_by(
       user_id=current_user.id, album_id=album_id
   ).count()

   If current_count >= 3:
   → return {"status": "limit_reached"}
   (JavaScript shows a warning message to the user)

4. Create new AlbumMood row
   → return {"status": "added"}
```

**Why is the limit enforced in the route, not the model?**  
The database constraint (UniqueConstraint) prevents duplicates. But "maximum 3 tags per user per album" is a business rule that requires counting existing rows before inserting — which is application logic, not a constraint the database can enforce directly.

Mood tag data is **public** — the aggregated counts are visible to all users on the album detail page.

---

## 9. Album Detail

---

### `GET /album/<id>`

**Function:** `album_detail(album_id)`  
**Login required:** Yes

The most data-heavy route. Assembles everything needed to render the full album detail page.

---

#### Step 1 — Fetch the album

```python
album = Album.query.get_or_404(album_id)
```

If the album ID doesn't exist in the database, returns a 404 page.

---

#### Step 2 — Stamp last_viewed_at

Every time a user visits an album detail page, the route records it:

```python
user_album = UserAlbum.query.filter_by(
    user_id=current_user.id, album_id=album.id
).first()

if user_album:
    user_album.last_viewed_at = datetime.utcnow()
else:
    user_album = UserAlbum(
        user_id=current_user.id,
        album_id=album.id,
        last_viewed_at=datetime.utcnow(),
    )
    db.session.add(user_album)

db.session.commit()
```

This timestamp powers the "Albums you visited" section on the dashboard. A `UserAlbum` row is created even if the user hasn't rated the album yet.

---

#### Step 3 — Lazy-load tracklist from Spotify

```python
if not album.tracklist:
    try:
        result = app.spotify.album(album.spotify_id)
        raw_tracks = result.get("tracks", {}).get("items", [])
        tracks_data = [
            {
                "track_number": t.get("track_number"),
                "name":         t.get("name"),
                "duration_ms":  t.get("duration_ms", 0),
            }
            for t in raw_tracks
        ]
        album.tracklist    = json.dumps(tracks_data)
        album.total_tracks = len(tracks_data)
        album.duration_ms  = sum(t["duration_ms"] for t in tracks_data)
        db.session.commit()
    except Exception:
        pass  # if Spotify is down, continue without tracklist
```

When an album is first added to a collection, only basic data (name, artist, image) is saved. The full tracklist is fetched from Spotify the first time anyone visits the album detail page and then cached in `album.tracklist` as a JSON string. Subsequent visits use the cached data — no Spotify call needed.

The `try/except` means the page still renders even if Spotify is unreachable.

---

#### Step 4 — Parse the tracklist

```python
raw = json.loads(album.tracklist) if album.tracklist else []
tracks = [
    {**t, "duration": ms_to_duration(t.get("duration_ms", 0))}
    for t in raw
]
```

Parses the JSON string into a Python list and adds a formatted `duration` string (e.g. `"4:32"`) to each track dict using `ms_to_duration()`.

---

#### Step 5 — Ratings

```python
user_rating = user_album.rating if user_album else None
user_notes  = user_album.notes  if user_album else None
total_likes    = UserAlbum.query.filter_by(album_id=album.id, rating=RATING_LIKE).count()
total_dislikes = UserAlbum.query.filter_by(album_id=album.id, rating=RATING_DISLIKE).count()
```

Gets the current user's personal rating and notes, plus community-wide totals.

---

#### Step 6 — Mood tag aggregation

```python
mood_counts = (
    db.session.query(MoodTag, func.count(AlbumMood.id).label("count"))
    .join(AlbumMood, AlbumMood.mood_tag_id == MoodTag.id)
    .filter(AlbumMood.album_id == album.id)
    .group_by(MoodTag.id)
    .order_by(func.count(AlbumMood.id).desc())
    .all()
)
```

Counts how many times each mood tag has been applied to this album across all users. Returns a list of `(MoodTag object, count)` tuples ordered by popularity. The template renders this as the mood profile bar on the album page.

Also fetches which tags the current user has applied (`user_mood_ids`) for pre-highlighting, and groups all 15 mood tags by category for the tag picker.

---

#### Step 7 — Comments

```python
comments = (
    Comment.query
    .filter_by(album_id=album.id, parent_id=None)
    .order_by(Comment.created_at.desc())
    .all()
)
```

Fetches only **top-level comments** (where `parent_id = None`). Replies are loaded automatically when the template accesses `comment.replies` — SQLAlchemy follows the self-referential relationship and fetches them.

Then builds `user_votes`, a dict of `{comment_id: vote_value}` for every comment and reply visible on the page. This lets the template highlight which vote buttons the user has already clicked.

```python
def collect_ids(comment_list):
    ids = []
    for c in comment_list:
        ids.append(c.id)
        ids.extend(collect_ids(c.replies))  # recurse into replies
    return ids

all_ids = collect_ids(comments)
vote_rows = CommentVote.query.filter(
    CommentVote.user_id == current_user.id,
    CommentVote.comment_id.in_(all_ids),
).all()
user_votes = {v.comment_id: v.value for v in vote_rows}
```

---

#### Template variables passed to `album_detail.html`

| Variable | Description |
|----------|-------------|
| `album` | The Album object |
| `tracks` | List of track dicts with `duration` string added |
| `album_duration` | Formatted total duration e.g. `"42:17"` |
| `user_rating` | `1`, `-1`, or `None` |
| `user_notes` | String or `None` |
| `total_likes` | Integer community like count |
| `total_dislikes` | Integer community dislike count |
| `mood_counts` | List of `(MoodTag, count)` tuples |
| `user_mood_ids` | List of tag IDs the user has applied |
| `moods_by_category` | Dict `{category: [MoodTag, ...]}` for the picker |
| `comments` | Top-level Comment objects (replies via `.replies`) |
| `user_votes` | Dict `{comment_id: 1 or -1}` |
| `RATING_LIKE` | The constant `1` |
| `RATING_DISLIKE` | The constant `-1` |

---

## 10. Comments

---

### `POST /comment`

**Function:** `post_comment()`  
**Login required:** Yes  
**Called via:** Regular form POST (page reloads)

Posts a new comment or reply.

```
1. Read from form data:
   - album_id
   - content (the comment text)
   - parent_id (optional — present only for replies)

2. Validate: if content is empty → flash warning, redirect to dashboard

3. Create Comment row:
   Comment(
       content=content,
       user_id=current_user.id,
       album_id=int(album_id),
       parent_id=int(parent_id) if parent_id else None
   )

4. db.session.add(comment)
   db.session.commit()

5. Redirect back to the album detail page, anchored to #comments
   url_for("album_detail", album_id=album_id) + "#comments"
```

Unlike rating and voting, comments use a regular form POST rather than AJAX. The page reloads after posting. The `#comments` anchor in the redirect URL scrolls the browser back down to the comment section automatically.

**Threading:** If `parent_id` is provided, the new comment is a reply. The template renders it indented under the parent. If `parent_id` is `None`, it appears as a new top-level comment.

---

### `POST /vote_comment`

**Function:** `vote_comment()`  
**Login required:** Yes  
**Called via:** AJAX only — always returns JSON

Upvotes or downvotes a comment.

**Input:**
- `comment_id` — ID of the comment
- `value` — must be `"1"` (upvote) or `"-1"` (downvote)

**Logic:**

```
1. Validate inputs

2. Fetch the Comment (404 if not found)

3. Look for an existing vote:
   existing = CommentVote.query.filter_by(
       user_id=current_user.id, comment_id=comment_id
   ).first()

4. Three cases:

   CASE A — existing vote, same direction:
   → user clicked the same button again (un-vote)
   → db.session.delete(existing)

   CASE B — existing vote, opposite direction:
   → user switched from upvote to downvote or vice versa
   → existing.value = new_value

   CASE C — no existing vote:
   → create new CommentVote row

5. db.session.commit()

6. Return {"status": "ok", "score": comment.score}
```

The `comment.score` property is computed at this point:
```python
@property
def score(self):
    return sum(v.value for v in self.votes)
```

JavaScript receives the new `score` and updates the number displayed next to the comment's vote buttons.

---

## 11. Search and Discovery

---

### `GET /search`

**Function:** `search()`  
**Login required:** Yes  
**Query parameters:** `query`, `offset`

Searches Spotify for albums and displays results.

```
1. Read query and offset from URL parameters:
   query  = request.args.get("query", "").strip()
   offset = int(request.args.get("offset", 0))

2. If query is not empty:
   Call Spotify API:
   results = app.spotify.search(q=query, type="album", limit=12, offset=offset)

   Build albums list from response:
   For each item in results["albums"]["items"]:
   {
     "spotify_id":   item["id"],
     "name":         item["name"],
     "artist":       joined artist names,
     "artist_id":    first artist's Spotify ID,
     "release_date": item["release_date"],
     "image_url":    first image URL,
   }

3. Fetch user's collections for the Add to Collection modal

4. Get user's ratings dict

5. For each result album, check if it already exists in the local database:
   local = Album.query.filter_by(spotify_id=...).first()
   album["local_id"]    = local.id if local else None
   album["user_rating"] = ratings.get(local.id) if local else None

   This lets the template:
   - Show a link to the album detail page if it's in the database
   - Show the user's current rating badge if they've rated it

6. Render search_results.html with:
   - albums list
   - query string (so the search box stays filled in)
   - offset (so Load More button can calculate the next offset)
   - has_more = len(albums) == 12  (if we got a full page, there's probably more)
   - collections (for the Add to Collection modal)
```

**The `offset` parameter** enables pagination. The first search uses `offset=0` and gets results 1–12. Clicking "Load More" navigates to the same URL with `offset=12`, getting results 13–24, and so on.

`has_more` is a simple heuristic — if we received exactly 12 results, it's likely there are more. If we received fewer than 12, we've reached the end.

---

### `GET /artist/<spotify_artist_id>`

**Function:** `artist_page(spotify_artist_id)`  
**Login required:** Yes

Fetches and displays an artist's profile and full discography. All data comes live from Spotify — there is no Artist model in the database.

```
1. Call Spotify API twice:
   artist_data = app.spotify.artist(spotify_artist_id)
   albums_data = app.spotify.artist_albums(spotify_artist_id, album_type="album", limit=20)

2. Build artist dict:
   {
     "name":      artist_data["name"],
     "image_url": first image URL,
     "followers": artist_data["followers"]["total"],
     "genres":    artist_data["genres"],
   }

3. Build albums list from discography:
   [{spotify_id, name, release_date, image_url, total_tracks}, ...]

4. Check which albums exist in the local database:
   spotify_ids  = [a["spotify_id"] for a in albums]
   local_albums = Album.query.filter(Album.spotify_id.in_(spotify_ids)).all()
   local_by_sid = {a.spotify_id: a for a in local_albums}

5. Attach local data to each album dict:
   album["local_id"]    = local.id if local else None
   album["user_rating"] = ratings.get(local.id) if local else None

6. Render artist.html

If any Spotify API call fails:
   flash error message
   redirect to dashboard
```

The entire route is wrapped in a `try/except`. If Spotify is unavailable or the artist ID is invalid, the user gets an error message and is redirected to the dashboard rather than seeing a crash page.