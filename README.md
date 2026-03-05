# AlbumRank — Project Documentation

This document explains how the entire project works, from the database
to the templates. It is written so that a complete beginner can follow along.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Folder Structure](#2-folder-structure)
3. [How Flask Works](#3-how-flask-works)
4. [The Database — Models](#4-the-database--models)
5. [The Models Explained](#5-the-models-explained)
6. [How Routes Work](#6-how-routes-work)
7. [How Templates Work](#7-how-templates-work)
8. [How CSS Works](#8-how-css-works)
9. [Setting Up the Project](#9-setting-up-the-project)
10. [Flask-Migrate — Managing Database Changes](#10-flask-migrate--managing-database-changes)
11. [Key Concepts for Beginners](#11-key-concepts-for-beginners)
12. [Common Errors and Fixes](#12-common-errors-and-fixes)

---

## 1. Project Overview

AlbumRank is a web application where users can:
- Search for albums using the Spotify API
- Add albums to personal collections
- Like or dislike albums
- Apply mood tags to albums (shared with all users)
- Comment on albums and vote on comments
- View album details including tracklist

The app is built with:
- **Flask** — Python web framework (handles routing and logic)
- **SQLAlchemy** — database library (handles data storage)
- **Jinja2** — templating engine (turns Python data into HTML)
- **Spotify API** — provides album data

---

## 2. Folder Structure

```
project/
│
├── ecouter.py              # Main app file — all routes live here
├── config.py               # App configuration (database URL, secret key)
├── forms.py                # Login and signup form definitions
├── DOCS.md                 # This file
│
├── models/                 # Database models (one file per table)
│   ├── __init__.py         # Exports all models for easy importing
│   ├── database.py         # Creates the db object
│   ├── user.py             # User accounts
│   ├── album.py            # Albums from Spotify
│   ├── playlist.py         # Collections (playlists)
│   ├── user_album.py       # Per-user rating and notes on an album
│   ├── mood.py             # Mood tags and which user applied them
│   └── comment.py          # Comments and votes on comments
│
├── templates/              # HTML files (one per page)
│   ├── landing.html        # Public landing page
│   ├── login.html          # Login page
│   ├── signup.html         # Signup page
│   ├── dashboard.html      # Main page after login
│   ├── collections.html    # List of user's collections
│   ├── view_collection.html # One collection's albums
│   ├── create_collection.html
│   ├── search_results.html
│   └── album_detail.html
│
└── static/                 # CSS and JavaScript files
    ├── global.css          # All CSS variables — import this in every CSS file
    ├── home.css            # Dashboard and search pages
    ├── landing.css         # Landing page
    ├── login-signup.css    # Login and signup pages
    ├── playlists.css       # Collections list page
    ├── create_playlist.css # Create collection page
    └── view_playlist.css   # View single collection page
```

---

## 3. How Flask Works

Flask is a Python web framework. The basic idea is:

1. A user visits a URL in their browser (e.g. `/dashboard`)
2. Flask matches that URL to a Python function called a **route**
3. The route runs some logic (e.g. fetches data from the database)
4. The route returns an HTML page (rendered from a template)

A basic route looks like this:

```python
@app.route('/dashboard')
def dashboard():
    # This function runs when someone visits /dashboard
    albums = Album.query.all()   # get all albums from the database
    return render_template('dashboard.html', albums=albums)
    # render_template fills in the HTML template with the albums data
```

The `@app.route('/dashboard')` line is called a **decorator** — it tells Flask
which URL should trigger this function.

---

## 4. The Database — Models

The database stores all the app's data permanently. We use SQLAlchemy,
which lets us write Python classes instead of raw SQL.

Each Python class represents one **table** in the database.
Each instance of that class represents one **row** in that table.

For example:
```python
# This creates a new user row in the database
new_user = User(username='alice', email='alice@example.com')
db.session.add(new_user)
db.session.commit()
```

### Relationships

Tables are connected to each other using **foreign keys** and **relationships**.

- A `Playlist` has a `user_id` column that points to the `User` who owns it.
- This is called a **one-to-many** relationship: one user, many playlists.

- A `Playlist` can contain many `Albums`, and an `Album` can be in many
  playlists. This is called a **many-to-many** relationship.
  We handle this with a join table called `collection_albums`.

---

## 5. The Models Explained

### User
Stores account information. Passwords are hashed — never stored as plain text.

| Column        | Type    | Description                          |
|---------------|---------|--------------------------------------|
| id            | Integer | Unique ID, set automatically         |
| username      | String  | Displayed name, must be unique       |
| email         | String  | Used to log in, must be unique       |
| password_hash | String  | Hashed password (not readable)       |
| created_at    | DateTime| When the account was created         |

---

### Album
Stores albums fetched from the Spotify API. One row per album, shared across
all users. Per-user data lives in `UserAlbum`, not here.

| Column       | Type    | Description                              |
|--------------|---------|------------------------------------------|
| id           | Integer | Unique ID                                |
| spotify_id   | String  | Spotify's ID for this album              |
| name         | String  | Album title                              |
| artist       | String  | Artist name(s)                           |
| artist_id    | String  | Spotify artist ID (for artist page)      |
| release_date | String  | Format: YYYY-MM-DD                       |
| image_url    | String  | Album cover image URL                    |
| tracklist    | Text    | JSON string of tracks (name + duration)  |
| duration_ms  | Integer | Total album length in milliseconds       |
| total_tracks | Integer | Number of tracks                         |

**Note on tracklist:** The tracklist is stored as a JSON string because SQLite
does not have a native array type. In your route, parse it like this:
```python
import json
tracks = json.loads(album.tracklist) if album.tracklist else []
```
Then pass `tracks` to the template.

---

### Playlist (Collection)
A collection of albums belonging to one user.

| Column      | Type    | Description                                   |
|-------------|---------|-----------------------------------------------|
| id          | Integer | Unique ID                                     |
| name        | String  | Collection name                               |
| description | Text    | Optional description written by the user      |
| is_public   | Boolean | If True, other users can view this collection |
| user_id     | Integer | Foreign key — which user owns this            |
| created_at  | DateTime|                                               |

---

### UserAlbum
The per-user relationship to an album. One row per user per album.
This is where rating and personal notes are stored.

| Column    | Type    | Description                                  |
|-----------|---------|----------------------------------------------|
| id        | Integer | Unique ID                                    |
| user_id   | Integer | Foreign key to User                          |
| album_id  | Integer | Foreign key to Album                         |
| rating    | Integer | 1 = Like, -1 = Dislike, None = not rated yet |
| notes     | Text    | Private note — only visible to this user     |

**To change the rating system later** (e.g. to 5 stars), only two things change:
1. Update the `rating` column to allow values 1–5
2. Update the rating buttons in the template

Nothing else in the codebase needs to change.

---

### MoodTag
A fixed list of mood tags. Seeded once into the database at startup.

| Column   | Type   | Description                     |
|----------|--------|---------------------------------|
| id       | Integer| Unique ID                       |
| name     | String | e.g. "Hype", "Peaceful", "Sad"  |
| category | String | e.g. "Energetic", "Calm"        |

The full list (15 tags across 5 categories):
- Energetic: Hype, Party, Pumped
- Emotional: Sad, Melancholic, Reflective
- Calm: Peaceful, Ambient, Focused
- Dark: Gritty, Moody, Intense
- Romantic: Warm, Passionate, Dreamy

---

### AlbumMood
Records which user applied which mood tag to which album.
These are public — they aggregate to show the mood profile of an album.

| Column      | Type    | Description                                |
|-------------|---------|--------------------------------------------|
| id          | Integer | Unique ID                                  |
| user_id     | Integer | Foreign key to User                        |
| album_id    | Integer | Foreign key to Album                       |
| mood_tag_id | Integer | Foreign key to MoodTag                     |

**Limit:** A user can apply a maximum of 3 mood tags per album.
This is enforced in the route before saving.

---

### Comment
A comment posted on an album detail page. Can be a reply to another comment.

| Column    | Type    | Description                                        |
|-----------|---------|----------------------------------------------------|
| id        | Integer | Unique ID                                          |
| content   | Text    | The comment text                                   |
| user_id   | Integer | Foreign key to User                                |
| album_id  | Integer | Foreign key to Album                               |
| parent_id | Integer | Foreign key to another Comment (None = top-level)  |
| created_at| DateTime|                                                    |

The `score` property on a Comment calculates upvotes minus downvotes automatically.

---

### CommentVote
One vote per user per comment. Toggling works by deleting the row.

| Column     | Type    | Description                   |
|------------|---------|-------------------------------|
| id         | Integer | Unique ID                     |
| user_id    | Integer | Foreign key to User           |
| comment_id | Integer | Foreign key to Comment        |
| value      | Integer | 1 = upvote, -1 = downvote     |

---

## 6. How Routes Work

All routes are defined in `ecouter.py` inside the `create_app()` function.

### Common patterns you will see:

**Getting data from the database:**
```python
album = Album.query.get_or_404(album_id)
# get_or_404 returns the album if it exists, or shows a 404 page if not
```

**Checking who is logged in:**
```python
@login_required          # redirect to login page if not logged in
def my_route():
    current_user.id      # the ID of the logged-in user
```

**Returning JSON (for AJAX requests from JavaScript):**
```python
return jsonify({'status': 'ok', 'message': 'Saved'})
```

**Sending data to a template:**
```python
return render_template('dashboard.html',
    collections=collections,   # available as {{ collections }} in the template
    ratings=ratings            # available as {{ ratings }} in the template
)
```

---

## 7. How Templates Work

Templates are HTML files in the `templates/` folder. They use Jinja2 syntax
to display Python data.

### Basic Jinja2 syntax:

```html
<!-- Display a variable -->
<h1>{{ album.name }}</h1>

<!-- Loop through a list -->
{% for album in albums %}
    <p>{{ album.name }}</p>
{% endfor %}

<!-- Conditional -->
{% if user_rating %}
    <p>You rated this album.</p>
{% else %}
    <p>You have not rated this album yet.</p>
{% endif %}
```

### Passing data safely to JavaScript:

When you need to pass a Python value into a JavaScript function in an HTML
attribute, use the `data-` attribute pattern to avoid quoting errors:

```html
<!-- In the template: -->
<button class="btn-open-rating"
        data-album-id="{{ album.id }}"
        data-album-name="{{ album.name | e }}"
        data-album-artist="{{ album.artist | e }}">
    Rate
</button>
```

```javascript
// In your JavaScript:
document.querySelectorAll('.btn-open-rating').forEach(btn => {
    btn.addEventListener('click', () => {
        const id     = btn.dataset.albumId;
        const name   = btn.dataset.albumName;
        const artist = btn.dataset.albumArtist;
        openRatingModal(id, name, artist);
    });
});
```

**Why not inline onclick?**
If an album is named "Doja Cat's Planet Her", the single quote breaks the
JavaScript string. The `data-` attribute approach avoids this completely.
The `| e` filter escapes HTML special characters safely.

---

## 8. How CSS Works

### global.css
This file defines all CSS variables (colours, fonts, spacing) and shared
components (nav bar, album grid, buttons, modals, toast).

Every other CSS file starts with:
```css
@import url('global.css');
```

### To change a colour across the whole app:
Open `global.css` and change the variable in `:root`. For example:
```css
--color-accent: #ff5f6d;   /* change this one value */
```
Every button, link, and highlight that uses `var(--color-accent)` will update.

### File responsibilities:
| File               | What it styles                          |
|--------------------|-----------------------------------------|
| global.css         | Everything shared (nav, cards, buttons) |
| home.css           | Dashboard and search results pages      |
| landing.css        | Public landing page                     |
| login-signup.css   | Login and signup forms                  |
| playlists.css      | Collections list page                   |
| create_playlist.css| Create collection form                  |
| view_playlist.css  | Single collection view                  |

---

## 9. Setting Up the Project

```bash
# 1. Clone the repo and enter the folder
cd ACS-2930-Album-Platform

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate      # Mac/Linux
venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create your .env file (never commit this to GitHub)
# It should contain:
# CLIENT_ID=your_spotify_client_id
# CLIENT_SECRET=your_spotify_client_secret
# SECRET_KEY=any_long_random_string

# 5. Set up the database
flask db init      # only needed once, creates the migrations/ folder
flask db migrate -m "initial schema"
flask db upgrade

# 6. Run the app
flask run
```

---

## 10. Flask-Migrate — Managing Database Changes

Flask-Migrate tracks changes to your models and updates the database safely
without deleting existing data.

### Setup (one time only):
Add these two lines to `ecouter.py` after `init_db(app)`:
```python
from flask_migrate import Migrate
migrate = Migrate(app, db)
```

Install it:
```bash
pip install flask-migrate
```

### Every time you change a model:
```bash
flask db migrate -m "describe what you changed"
flask db upgrade
```

For example, if you add a `genre` column to `Album`:
```bash
flask db migrate -m "add genre to album"
flask db upgrade
```

### The three commands explained:
- `flask db init` — creates the `migrations/` folder. Run once ever.
- `flask db migrate` — detects what changed and writes a migration file.
- `flask db upgrade` — applies the migration to the actual database.

**Important:** Commit the `migrations/` folder to Git so all teammates
get the same database structure when they pull.

---

## 11. Key Concepts for Beginners

### What is a foreign key?
A foreign key is a column that points to a row in another table.
For example, `user_id` in `Playlist` points to the `id` column in `User`.
This is how we know which user owns which playlist.

### What is a relationship?
A SQLAlchemy relationship lets you access related data as a Python attribute
without writing SQL. For example:
```python
user.collections    # returns all Playlist rows belonging to this user
playlist.albums     # returns all Album rows in this playlist
album.user_albums   # returns all UserAlbum rows for this album
```

### What is a unique constraint?
It tells the database to reject duplicate entries. For example,
`UserAlbum` has a unique constraint on `(user_id, album_id)` — this
means one user cannot have two rating rows for the same album.

### What is a backref?
A backref automatically creates a reverse relationship. For example:
```python
# In UserAlbum:
db.relationship('User', backref='user_albums', ...)
```
This means you can access `user.user_albums` even though the relationship
is defined on `UserAlbum`, not `User`.

### What is AJAX?
AJAX lets JavaScript send data to the server and receive a response
without reloading the page. We use it for rating albums, adding to
collections, and voting on comments. The server returns JSON, and
JavaScript updates the page with the result.

---

## 12. Common Errors and Fixes

### `ImportError: cannot import name 'X' from 'models'`
You added a new model but forgot to import it in `models/__init__.py`.
Add the import there and add it to `__all__`.

### `sqlalchemy.exc.OperationalError: no such column`
You added a column to a model but did not run the migration.
Run `flask db migrate` and `flask db upgrade`.

### `KeyError` or `AttributeError` in a template
The variable you are trying to use in the template was not passed from
the route. Check the `render_template(...)` call in `ecouter.py` and
make sure the variable name matches.

### JavaScript `SyntaxError` in onclick attribute
You are passing a Python string directly into an inline JavaScript call.
Use `data-` attributes instead — see section 7 above.

### `404 Not Found` on a route
Either the URL is wrong, or you forgot the `@login_required` decorator
is redirecting you to login first.