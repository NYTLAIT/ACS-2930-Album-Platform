Ecouter — Project Documentation
Overview
Ecouter is a Flask web application for people who listen to albums, not just singles.
Users build collections, rate albums, tag moods, leave threaded comments, and discover
what other listeners are enjoying. All album and artist data is pulled live from the
Spotify API.

Tech Stack
LayerTechnologyBackendPython 3.9+, FlaskDatabaseSQLite (dev) via SQLAlchemy ORMAuthFlask-Login, Werkzeug password hashFormsFlask-WTF with CSRF protectionMusic dataSpotipy (Spotify Web API client)FrontendJinja2 templates, plain CSS, minimal JS (no framework)

Project Structure
Ecouter/
├── ecouter.py          Application factory and all routes
├── forms.py            Flask-WTF form classes (LoginForm, SignupForm)
├── config.py           DevelopmentConfig with env var loading
├── models/
│   ├── __init__.py     Single import point for all models
│   ├── database.py     Shared SQLAlchemy instance
│   ├── user.py         User model
│   ├── album.py        Album model
│   ├── collection.py   Collection model + collection_albums join table
│   ├── user_album.py   UserAlbum model (ratings, notes, last viewed)
│   ├── mood.py         MoodTag + AlbumMood models + seed function
│   └── comment.py      Comment + CommentVote models
├── templates/
│   ├── landing.html    Public landing page
│   ├── login.html      Login page
│   ├── signup.html     Sign up page
│   ├── dashboard.html  Main dashboard / discovery hub
│   ├── search_results.html  Spotify search results
│   ├── collections.html     Collections list
│   ├── create_collection.html  New collection form
│   ├── view_collection.html    Single collection view
│   ├── album_detail.html       Album detail with sidebar
│   └── artist.html             Artist discography page
└── static/
    ├── global.css      Design tokens, resets, shared components
    ├── landing.css     Landing page (self-contained)
    ├── auth.css        Login/signup pages (self-contained)
    ├── dashboard.css   Dashboard styles
    ├── search.css      Search results + collection modal
    ├── collections.css Collections list, create, view pages
    ├── album_detail.css Album detail two-column layout
    └── artist.css      Artist hero + discography grid

Environment Variables
Create a .env file in the project root:
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
SECRET_KEY=a_long_random_string_for_flask_sessions
DATABASE_URL=sqlite:///Ecouter.db
Get Spotify credentials at https://developer.spotify.com/dashboard

Setup
bash# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install flask flask-login flask-sqlalchemy flask-wtf spotipy python-dotenv werkzeug

# Run the app
flask run
On first run, db.create_all() creates all tables and seed_mood_tags() inserts
the 15 mood tags. No migration step needed for a fresh install.

Database Reset
When models change and you want a clean slate:
bash# Clear Python cache (prevents stale .pyc files causing import errors)
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete

# Delete the database
rm Ecouter.db

# Restart — tables and mood tags are recreated automatically
flask run

Data Model
User
One account per email address. Owns collections, ratings, notes, mood tags, and comments.
Album
One row per unique Spotify album, shared across all users. Created the first time any
user adds it to a collection. Tracklist is fetched from Spotify on first visit and
cached as a JSON string in the tracklist column.
Collection
Belongs to one User. Contains many Albums via the collection_albums join table.
Can be public (visible to all logged-in users) or private (owner only).
last_opened_at is stamped whenever the owner views or adds to it — used by the
dashboard recent activity section.
UserAlbum
The join between a User and an Album that carries data. Stores:

rating — 1 (like), -1 (dislike), or None
notes — private text, only visible to the owner
last_viewed_at — stamped on every album detail page visit

One row per user per album (UniqueConstraint).
MoodTag
Fixed lookup table of 15 tags across 5 categories, seeded on startup:

Energetic: Hype, Upbeat, Motivating
Emotional: Melancholic, Heartfelt, Nostalgic
Calm: Relaxing, Focused, Dreamy
Dark: Brooding, Intense, Haunting
Romantic: Sensual, Tender, Euphoric

AlbumMood
Links a User, Album, and MoodTag. One user can apply up to 3 tags per album
(enforced in the route). Mood data is public — aggregated counts are shown to
all users on the album detail page.
Comment
Supports threading via a self-referential parent_id foreign key.

parent_id = None → top-level comment
parent_id = int → reply to that comment

Score is computed at runtime: sum of all CommentVote values.
CommentVote
One vote per user per comment. value is 1 (upvote) or -1 (downvote).
Toggle logic: same vote removes it, opposite vote switches it.

Routes
MethodURLDescriptionGET/Landing page (redirects if logged in)GET/POST/signupCreate accountGET/POST/loginLog inGET/logoutLog outGET/dashboardDashboard / discovery hubGET/collectionsList user's collectionsGET/collection/<id>View a single collectionGET/POST/create_collectionCreate a new collectionPOST/edit_collection/<id>Update collection name/description/publicPOST/delete_collection/<id>Delete a collectionPOST/add_to_collectionAdd album to collection (AJAX)POST/rate_albumLike or dislike an album (AJAX)POST/save_noteSave private note on album (AJAX)POST/tag_moodToggle mood tag on album (AJAX)GET/album/<id>Album detail pagePOST/commentPost a comment or replyPOST/vote_commentVote on a comment (AJAX)GET/searchSearch Spotify for albumsGET/artist/<spotify_artist_id>Artist page

JavaScript
JS is used only where a page reload would break the user experience:

Rating buttons — Like/Dislike toggle without losing page state
Mood tags — toggle + limit enforcement without reload
Private notes — save on button click with status feedback
Comment votes — score updates inline
Reply forms — toggle visibility without navigation
Add to Collection modal — stays on search results page

All other interactions (forms, navigation, back links) are plain HTML and Flask.
No JS framework is used. All JS uses const/let — no var.

Design System
All design tokens are CSS custom properties defined in global.css:
css--bg, --surface, --surface-2  Background layers
--border                      Border colour
--accent, --accent-warm       Primary red and warm gold
--text, --muted               Text colours
--like, --dislike             Green and red for ratings
--r-sm, --r-md, --r-lg, --r-pill  Border radii
--font-body, --font-display   Roboto and Montserrat
--ease                        Default transition timing

Known Limitations

SQLite is used for development. Switch to PostgreSQL for production by changing
DATABASE_URL in config.
Spotify API calls are made on page load with no caching layer. Under heavy load
consider adding Redis or a simple in-memory cache.
The Spotify client credentials flow does not support user-specific data (play counts,
saved tracks). Only public album and artist data is available.