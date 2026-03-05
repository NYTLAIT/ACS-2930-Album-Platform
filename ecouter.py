"""
ecouter.py

Main Flask application file.
All routes are registered inside create_app() using the application factory
pattern — this means the app is only created when you call create_app(),
not at import time. This makes testing and configuration easier.

Usage:
    flask run          (development)
    python ecouter.py  (direct)

Environment variables required in .env:
    CLIENT_ID      Spotify API client ID
    CLIENT_SECRET  Spotify API client secret
    SECRET_KEY     Flask session secret key
"""

import json
from datetime import datetime, timedelta

import spotipy
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from flask_wtf import CSRFProtect

from spotipy.oauth2 import SpotifyClientCredentials
from sqlalchemy import func

from config import DevelopmentConfig
from models import (
    AlbumMood, Album, Collection, collection_albums,
    Comment, CommentVote,
    MoodTag, UserAlbum,
    User, RATING_LIKE, RATING_DISLIKE,
    db, init_db, seed_mood_tags,
)
from forms import SignupForm, LoginForm

import os
from dotenv import load_dotenv
load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# Application factory
# ─────────────────────────────────────────────────────────────────────────────

def create_app(config_class=DevelopmentConfig):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # ── Initialize CSRF ─────────────────────────────
    csrf = CSRFProtect(app)
    if not app.config.get("WTF_CSRF_ENABLED", True):
        csrf._disable_on_request = True

    # ── Database ──────────────────────────────────────────────
    init_db(app)

    # ── Jinja2 custom test ────────────────────────────────────
    # Allows {% if value | ge(20) %} style tests in templates
    app.jinja_env.tests["ge"] = lambda value, other: value >= other

    # ── Flask-Login ───────────────────────────────────────────
    login_manager = LoginManager(app)
    login_manager.login_view = "login"
    login_manager.login_message = "Please log in to continue."
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # ── Spotify client ────────────────────────────────────────
    client_id = os.getenv('CLIENT_ID')
    client_secret = os.getenv('CLIENT_SECRET')
    auth_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
    app.spotify = spotipy.Spotify(auth_manager=auth_manager)

    # ── Seed mood tags on startup ─────────────────────────────
    with app.app_context():
        seed_mood_tags()

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def ms_to_duration(ms):
        """Convert milliseconds to a human-readable string like '4:32'."""
        if not ms:
            return None
        total_seconds = ms // 1000
        minutes       = total_seconds // 60
        seconds       = total_seconds % 60
        return f"{minutes}:{seconds:02d}"

    def get_user_ratings(user_id):
        """
        Return a dict of {album_id: rating} for all albums this user has rated.
        One query — call this once per page and pass the dict to the template.
        """
        rows = UserAlbum.query.filter_by(user_id=user_id).all()
        return {row.album_id: row.rating for row in rows}

    def get_user_mood_ids(user_id, album_id):
        """Return a list of mood_tag_ids the user has applied to this album."""
        rows = AlbumMood.query.filter_by(
            user_id=user_id, album_id=album_id
        ).all()
        return [row.mood_tag_id for row in rows]

    # ─────────────────────────────────────────────────────────────────────────
    # Auth routes
    # ─────────────────────────────────────────────────────────────────────────

    @app.route("/")
    def index():
        """Landing page. Redirect to dashboard if already logged in."""
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return render_template("landing.html")

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))

        form = SignupForm()

        if form.validate_on_submit():
            if User.query.filter_by(email=form.email.data).first():
                flash("An account with that email already exists.", "danger")
                return render_template("signup.html", form=form)

            if User.query.filter_by(username=form.username.data).first():
                flash("That username is already taken.", "danger")
                return render_template("signup.html", form=form)

            user = User(email=form.email.data, username=form.username.data)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Welcome to Ecouter!", "success")
            return redirect(url_for("dashboard"))

        return render_template("signup.html", form=form)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))

        form = LoginForm()

        if form.validate_on_submit():
            user = User.query.filter_by(email=form.email.data).first()
            if user and user.check_password(form.password.data):
                login_user(user)
                return redirect(url_for("dashboard"))
            flash("Incorrect email or password.", "danger")

        return render_template("login.html", form=form)

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash("You have been logged out.", "info")
        return redirect(url_for("login"))

    # ─────────────────────────────────────────────────────────────────────────
    # Dashboard — discovery hub
    # ─────────────────────────────────────────────────────────────────────────

    @app.route("/dashboard")
    @login_required
    def dashboard():
        """
        Main dashboard. Shows recent activity and discovery sections.

        Query parameters:
            moods     — comma-separated mood_tag_ids to filter discovery sections
            mood_mode — "any" (default) or "all"
        """
        # ── Mood filter ───────────────────────────────────────
        mood_param      = request.args.get("moods", "").strip()
        mood_mode       = request.args.get("mood_mode", "any")
        active_mood_ids = []

        if mood_param:
            try:
                active_mood_ids = [
                    int(x) for x in mood_param.split(",") if x.strip()
                ]
            except ValueError:
                active_mood_ids = []

        # ── Album IDs from public collections ─────────────────
        public_id_rows = (
            db.session.query(collection_albums.c.album_id)
            .join(Collection, Collection.id == collection_albums.c.collection_id)
            # .filter(Collection.is_public.is_(True))
            .distinct()
            .all()
        )
        public_album_ids = [row[0] for row in public_id_rows]

        # ── Apply mood filter ─────────────────────────────────
        def apply_mood_filter(base_ids):
            """Return the subset of base_ids that match the active mood filter."""
            if not active_mood_ids or not base_ids:
                return base_ids
            if mood_mode == "all":
                rows = (
                    db.session.query(AlbumMood.album_id)
                    .filter(
                        AlbumMood.album_id.in_(base_ids),
                        AlbumMood.mood_tag_id.in_(active_mood_ids),
                    )
                    .group_by(AlbumMood.album_id)
                    .having(
                        func.count(func.distinct(AlbumMood.mood_tag_id))
                        == len(active_mood_ids)
                    )
                    .all()
                )
            else:
                rows = (
                    db.session.query(AlbumMood.album_id)
                    .filter(
                        AlbumMood.album_id.in_(base_ids),
                        AlbumMood.mood_tag_id.in_(active_mood_ids),
                    )
                    .distinct()
                    .all()
                )
            return [r[0] for r in rows]

        filtered_ids = apply_mood_filter(public_album_ids)

        # ── Recent activity ───────────────────────────────────
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

        recent_collections = (
            Collection.query
            .filter(
                Collection.user_id == current_user.id,
                Collection.last_opened_at.isnot(None),
            )
            .order_by(Collection.last_opened_at.desc())
            .limit(4)
            .all()
        )
        if not recent_collections:
            recent_collections = (
                Collection.query
                .filter_by(user_id=current_user.id)
                .order_by(Collection.created_at.desc())
                .limit(4)
                .all()
            )

        # ── Discovery: Trending this week ─────────────────────
        one_week_ago  = datetime.now() - timedelta(days=7)
        trending_rows = (
            db.session.query(Album, func.count(UserAlbum.id).label("like_count"))
            .join(UserAlbum, UserAlbum.album_id == Album.id)
            .filter(
                Album.id.in_(filtered_ids) if filtered_ids else Album.id.in_([]),
                UserAlbum.rating == RATING_LIKE,
                UserAlbum.updated_at >= one_week_ago,
            )
            .group_by(Album.id)
            .order_by(func.count(UserAlbum.id).desc())
            .limit(12)
            .all()
        )
        trending = [{"album": r[0], "like_count": r[1]} for r in trending_rows]

        # ── Discovery: Top rated overall ──────────────────────
        top_rows = (
            db.session.query(Album, func.count(UserAlbum.id).label("like_count"))
            .join(UserAlbum, UserAlbum.album_id == Album.id)
            .filter(
                Album.id.in_(filtered_ids) if filtered_ids else Album.id.in_([]),
                UserAlbum.rating == RATING_LIKE,
            )
            .group_by(Album.id)
            .order_by(func.count(UserAlbum.id).desc())
            .limit(12)
            .all()
        )
        top_rated = [{"album": r[0], "like_count": r[1]} for r in top_rows]

        # ── Discovery: New arrivals ───────────────────────────
        new_arrivals = (
            Album.query
            .filter(
                Album.id.in_(filtered_ids) if filtered_ids else Album.id.in_([])
            )
            .order_by(Album.id.desc())
            .limit(12)
            .all()
        )

        # ── Discovery: Unrated by you ─────────────────────────
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
                Album.id.in_(filtered_ids) if filtered_ids else Album.id.in_([]),
                UserAlbum.rating == RATING_LIKE,
                Album.id.notin_(rated_by_me),
            )
            .group_by(Album.id)
            .order_by(func.count(UserAlbum.id).desc())
            .limit(12)
            .all()
        )
        unrated = [{"album": r[0], "like_count": r[1]} for r in unrated_rows]

        # ── User's own collections ────────────────────────────
        my_collections = (
            Collection.query
            .filter_by(user_id=current_user.id)
            .order_by(Collection.created_at.desc())
            .all()
        )

        ratings       = get_user_ratings(current_user.id)
        all_mood_tags = MoodTag.query.order_by(MoodTag.category, MoodTag.name).all()

        return render_template(
            "dashboard.html",
            recently_viewed=recently_viewed,
            recent_collections=recent_collections,
            trending=trending,
            top_rated=top_rated,
            new_arrivals=new_arrivals,
            unrated=unrated,
            collections=my_collections,
            ratings=ratings,
            all_mood_tags=all_mood_tags,
            active_mood_ids=active_mood_ids,
            mood_mode=mood_mode,
            no_public_albums=(len(public_album_ids) == 0),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Collections
    # ─────────────────────────────────────────────────────────────────────────

    @app.route("/collections")
    @login_required
    def collections():
        user_collections = (
            Collection.query
            .filter_by(user_id=current_user.id)
            .order_by(Collection.created_at.desc())
            .all()
        )
        return render_template("collections.html", collections=user_collections)

    @app.route("/collection/<int:collection_id>")
    @login_required
    def view_collection(collection_id):
        collection = Collection.query.get_or_404(collection_id)

        if not collection.is_public and collection.user_id != current_user.id:
            flash("That collection is private.", "danger")
            return redirect(url_for("collections"))

        # Stamp last_opened_at so the dashboard shows recent activity
        if collection.user_id == current_user.id:
            collection.last_opened_at = datetime.now()
            db.session.commit()

        ratings = get_user_ratings(current_user.id)

        return render_template(
            "view_collection.html",
            collection=collection,
            ratings=ratings,
            is_owner=(collection.user_id == current_user.id),
        )

    @app.route("/create_collection", methods=["GET", "POST"])
    @login_required
    def create_collection():
        """
        GET  — show the create form.
        POST — save the collection.
        POST via AJAX (X-Requested-With header) — return JSON for the search modal.
        """
        if request.method == "POST":
            name        = request.form.get("name", "").strip()
            description = request.form.get("description", "").strip()
            is_public   = request.form.get("is_public") == "on"

            if not name:
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return jsonify({"error": "Name is required"}), 400
                flash("Please enter a name for your collection.", "danger")
                return render_template("create_collection.html")

            new_col = Collection(
                name=name,
                description=description or None,
                is_public=is_public,
                user_id=current_user.id,
            )
            db.session.add(new_col)
            db.session.commit()

            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"id": new_col.id, "name": new_col.name})

            flash("Collection created.", "success")
            return redirect(url_for("collections"))

        return render_template("create_collection.html")

    @app.route("/edit_collection/<int:collection_id>", methods=["POST"])
    @login_required
    def edit_collection(collection_id):
        collection = Collection.query.get_or_404(collection_id)

        if collection.user_id != current_user.id:
            flash("You do not have permission to edit that collection.", "danger")
            return redirect(url_for("collections"))

        name        = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        is_public   = request.form.get("is_public") == "on"

        if name:
            collection.name = name
        collection.description = description or None
        collection.is_public   = is_public
        db.session.commit()

        flash("Collection updated.", "success")
        return redirect(url_for("view_collection", collection_id=collection.id))

    @app.route("/delete_collection/<int:collection_id>", methods=["POST"])
    @login_required
    def delete_collection(collection_id):
        collection = Collection.query.get_or_404(collection_id)

        if collection.user_id != current_user.id:
            flash("You do not have permission to delete that collection.", "danger")
            return redirect(url_for("collections"))

        db.session.delete(collection)
        db.session.commit()
        flash("Collection deleted.", "success")
        return redirect(url_for("collections"))

    # ─────────────────────────────────────────────────────────────────────────
    # Add album to collection
    # ─────────────────────────────────────────────────────────────────────────

    @app.route("/add_to_collection", methods=["POST"])
    @login_required
    def add_to_collection():
        """
        Creates the Album row if it does not exist yet,
        then appends it to the collection.
        Always called via AJAX — always returns JSON.
        """
        spotify_id    = request.form.get("spotify_id", "").strip()
        name          = request.form.get("name", "").strip()
        artist        = request.form.get("artist", "").strip()
        artist_id     = request.form.get("artist_id", "").strip()
        release_date  = request.form.get("release_date", "").strip()
        image_url     = request.form.get("image_url", "").strip()
        collection_id = request.form.get("collection_id")

        if not spotify_id or not collection_id:
            return jsonify({"error": "Missing required fields"}), 400

        collection = Collection.query.get_or_404(int(collection_id))
        if collection.user_id != current_user.id:
            return jsonify({"error": "Permission denied"}), 403

        # Create the album row if this is the first time we have seen it
        album = Album.query.filter_by(spotify_id=spotify_id).first()
        if not album:
            album = Album(
                spotify_id=spotify_id,
                name=name,
                artist=artist,
                artist_id=artist_id or None,
                release_date=release_date or None,
                image_url=image_url or None,
            )
            db.session.add(album)
            db.session.flush()  # get album.id before commit

        # Add to collection if not already there
        if album in collection.albums:
            return jsonify({
                "status": "exists",
                "message": f'Already in "{collection.name}"',
            })

        collection.albums.append(album)
        collection.last_opened_at = datetime.now()
        db.session.commit()

        return jsonify({
            "status": "added",
            "message": f'Added to "{collection.name}"',
            "album_id": album.id,
        })

    # ─────────────────────────────────────────────────────────────────────────
    # Ratings
    # ─────────────────────────────────────────────────────────────────────────

    @app.route("/rate_album", methods=["POST"])
    @login_required
    def rate_album():
        """
        Like or dislike an album. Always called via AJAX.
        Toggle behaviour: same rating removes it, opposite rating switches it.
        """
        album_id = request.form.get("album_id")
        rating   = request.form.get("rating")

        if not album_id or rating not in ("1", "-1"):
            return jsonify({"error": "Invalid input"}), 400

        album_id = int(album_id)
        rating   = int(rating)
        album    = Album.query.get_or_404(album_id)

        user_album = UserAlbum.query.filter_by(
            user_id=current_user.id, album_id=album_id
        ).first()

        if user_album:
            if user_album.rating == rating:
                # Same rating — remove it (toggle off)
                user_album.rating = None
                db.session.commit()
                return jsonify({"status": "removed", "rating": None})
            else:
                # Different rating — switch
                user_album.rating = rating
                db.session.commit()
                return jsonify({"status": "updated", "rating": rating})
        else:
            user_album = UserAlbum(
                user_id=current_user.id,
                album_id=album_id,
                rating=rating,
            )
            db.session.add(user_album)
            db.session.commit()
            return jsonify({"status": "added", "rating": rating})

    # ─────────────────────────────────────────────────────────────────────────
    # Notes
    # ─────────────────────────────────────────────────────────────────────────

    @app.route("/save_note", methods=["POST"])
    @login_required
    def save_note():
        """Save a private note on an album. Always called via AJAX."""
        album_id = request.form.get("album_id")
        notes    = request.form.get("notes", "").strip()

        if not album_id:
            return jsonify({"error": "Missing album_id"}), 400

        album_id  = int(album_id)
        user_album = UserAlbum.query.filter_by(
            user_id=current_user.id, album_id=album_id
        ).first()

        if user_album:
            user_album.notes = notes or None
        else:
            user_album = UserAlbum(
                user_id=current_user.id,
                album_id=album_id,
                notes=notes or None,
            )
            db.session.add(user_album)

        db.session.commit()
        return jsonify({"status": "ok"})

    # ─────────────────────────────────────────────────────────────────────────
    # Mood tags
    # ─────────────────────────────────────────────────────────────────────────

    @app.route("/tag_mood", methods=["POST"])
    @login_required
    def tag_mood():
        """Toggle a mood tag on an album. Always called via AJAX. Max 3 per user per album."""
        album_id    = request.form.get("album_id")
        mood_tag_id = request.form.get("mood_tag_id")

        if not album_id or not mood_tag_id:
            return jsonify({"error": "Missing fields"}), 400

        album_id    = int(album_id)
        mood_tag_id = int(mood_tag_id)

        existing = AlbumMood.query.filter_by(
            user_id=current_user.id,
            album_id=album_id,
            mood_tag_id=mood_tag_id,
        ).first()

        if existing:
            db.session.delete(existing)
            db.session.commit()
            return jsonify({"status": "removed"})

        # Enforce 3-tag limit
        current_count = AlbumMood.query.filter_by(
            user_id=current_user.id, album_id=album_id
        ).count()

        if current_count >= 3:
            return jsonify({"status": "limit_reached"})

        mood = AlbumMood(
            user_id=current_user.id,
            album_id=album_id,
            mood_tag_id=mood_tag_id,
        )
        db.session.add(mood)
        db.session.commit()
        return jsonify({"status": "added"})

    # ─────────────────────────────────────────────────────────────────────────
    # Album detail
    # ─────────────────────────────────────────────────────────────────────────

    @app.route("/album/<int:album_id>")
    @login_required
    def album_detail(album_id):
        album = Album.query.get_or_404(album_id)

        # Stamp last_viewed_at for recent activity on the dashboard
        user_album = UserAlbum.query.filter_by(
            user_id=current_user.id, album_id=album.id
        ).first()
        if user_album:
            user_album.last_viewed_at = datetime.now()
        else:
            user_album = UserAlbum(
                user_id=current_user.id,
                album_id=album.id,
                last_viewed_at=datetime.now(),
            )
            db.session.add(user_album)
        db.session.commit()

        # Lazy-load tracklist from Spotify on first visit, cache in db
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
                pass

        # Parse tracklist and add formatted duration to each track
        raw = json.loads(album.tracklist) if album.tracklist else []
        tracks = [
            {**t, "duration": ms_to_duration(t.get("duration_ms", 0))}
            for t in raw
        ]

        # Ratings and notes
        user_album  = UserAlbum.query.filter_by(
            user_id=current_user.id, album_id=album.id
        ).first()
        user_rating = user_album.rating if user_album else None
        user_notes  = user_album.notes  if user_album else None

        # Community rating totals
        total_likes    = UserAlbum.query.filter_by(album_id=album.id, rating=RATING_LIKE).count()
        total_dislikes = UserAlbum.query.filter_by(album_id=album.id, rating=RATING_DISLIKE).count()

        # Mood counts — aggregated across all users
        mood_counts = (
            db.session.query(MoodTag, func.count(AlbumMood.id).label("count"))
            .join(AlbumMood, AlbumMood.mood_tag_id == MoodTag.id)
            .filter(AlbumMood.album_id == album.id)
            .group_by(MoodTag.id)
            .order_by(func.count(AlbumMood.id).desc())
            .all()
        )

        user_mood_ids = get_user_mood_ids(current_user.id, album.id)

        all_mood_tags = MoodTag.query.order_by(MoodTag.category, MoodTag.name).all()
        moods_by_category = {}
        for tag in all_mood_tags:
            moods_by_category.setdefault(tag.category, []).append(tag)

        # Comments — top-level only, replies loaded via relationship
        comments = (
            Comment.query
            .filter_by(album_id=album.id, parent_id=None)
            .order_by(Comment.created_at.desc())
            .all()
        )

        # Current user's votes
        def collect_ids(comment_list):
            ids = []
            for c in comment_list:
                ids.append(c.id)
                ids.extend(collect_ids(c.replies))
            return ids

        user_votes = {}
        all_ids = collect_ids(comments)
        if all_ids:
            vote_rows = CommentVote.query.filter(
                CommentVote.user_id == current_user.id,
                CommentVote.comment_id.in_(all_ids),
            ).all()
            user_votes = {v.comment_id: v.value for v in vote_rows}

        return render_template(
            "album_detail.html",
            album=album,
            tracks=tracks,
            album_duration=ms_to_duration(album.duration_ms),
            user_rating=user_rating,
            user_notes=user_notes,
            total_likes=total_likes,
            total_dislikes=total_dislikes,
            mood_counts=mood_counts,
            user_mood_ids=user_mood_ids,
            moods_by_category=moods_by_category,
            comments=comments,
            user_votes=user_votes,
            RATING_LIKE=RATING_LIKE,
            RATING_DISLIKE=RATING_DISLIKE,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Comments
    # ─────────────────────────────────────────────────────────────────────────

    @app.route("/comment", methods=["POST"])
    @login_required
    def post_comment():
        album_id  = request.form.get("album_id")
        content   = request.form.get("content", "").strip()
        parent_id = request.form.get("parent_id") or None

        if not album_id or not content:
            flash("Comment cannot be empty.", "danger")
            return redirect(url_for("dashboard"))

        comment = Comment(
            content=content,
            user_id=current_user.id,
            album_id=int(album_id),
            parent_id=int(parent_id) if parent_id else None,
        )
        db.session.add(comment)
        db.session.commit()
        return redirect(url_for("album_detail", album_id=album_id) + "#comments")

    @app.route("/vote_comment", methods=["POST"])
    @login_required
    def vote_comment():
        """Toggle vote on a comment. Always called via AJAX."""
        comment_id = request.form.get("comment_id")
        value      = request.form.get("value")

        if not comment_id or value not in ("1", "-1"):
            return jsonify({"error": "Invalid input"}), 400

        comment_id = int(comment_id)
        value      = int(value)
        comment    = Comment.query.get_or_404(comment_id)

        existing = CommentVote.query.filter_by(
            user_id=current_user.id, comment_id=comment_id
        ).first()

        if existing:
            if existing.value == value:
                db.session.delete(existing)
            else:
                existing.value = value
        else:
            db.session.add(CommentVote(
                user_id=current_user.id,
                comment_id=comment_id,
                value=value,
            ))

        db.session.commit()
        return jsonify({"status": "ok", "score": comment.score})

    # ─────────────────────────────────────────────────────────────────────────
    # Search
    # ─────────────────────────────────────────────────────────────────────────

    @app.route("/search")
    @login_required
    def search():
        query  = request.args.get("query", "").strip()
        offset = int(request.args.get("offset", 0)) 
        albums = []

        if query:
            try:
                results = app.spotify.search(q=query, type="album", limit=10, offset=offset)
                for item in results.get("albums", {}).get("items", []):
                    albums.append({
                        "spotify_id":   item.get("id", ""),
                        "name":         item.get("name", "Unknown"),
                        "artist":       ", ".join(
                            a["name"] for a in item.get("artists", [])
                        ),
                        "artist_id":    item["artists"][0]["id"]
                                        if item.get("artists") else "",
                        "release_date": item.get("release_date", ""),
                        "image_url":    item["images"][0]["url"]
                                        if item.get("images") else None,
                    })
            except Exception as e:
                flash(f"Search failed: {e}", "danger")

        user_collections = (
            Collection.query
            .filter_by(user_id=current_user.id)
            .order_by(Collection.created_at.desc())
            .all()
        )

        ratings = get_user_ratings(current_user.id)

        if albums:
            spotify_ids  = [a["spotify_id"] for a in albums]
            local_albums = Album.query.filter(
                Album.spotify_id.in_(spotify_ids)
            ).all()
            local_by_sid = {a.spotify_id: a for a in local_albums}

            for album in albums:
                local = local_by_sid.get(album["spotify_id"])
                album["local_id"]    = local.id if local else None
                album["user_rating"] = ratings.get(local.id) if local else None

        return render_template(
            "search_results.html",
            albums=albums,
            query=query,
            collections=user_collections,
            offset=offset,         
            has_more=len(albums)==10
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Artist page
    # ─────────────────────────────────────────────────────────────────────────

    @app.route("/artist/<spotify_artist_id>")
    @login_required
    def artist_page(spotify_artist_id):
        try:
            artist_data = app.spotify.artist(spotify_artist_id)
            albums_data = app.spotify.artist_albums(
                spotify_artist_id, album_type="album", limit=10
            )

            images         = artist_data.get("images") or []
            followers_data = artist_data.get("followers") or {}
            followers      = (
                followers_data.get("total", 0)
                if isinstance(followers_data, dict)
                else 0
            )

            artist = {
                "name":      artist_data.get("name", "Unknown Artist"),
                "image_url": images[0]["url"] if images else None,
                "followers": followers,
                "genres":    artist_data.get("genres", []),
            }

            albums = []
            for item in albums_data.get("items", []):
                item_images = item.get("images") or []
                albums.append({
                    "spotify_id":   item["id"],
                    "name":         item.get("name", "Unknown"),
                    "release_date": item.get("release_date", ""),
                    "image_url":    item_images[0]["url"] if item_images else None,
                    "total_tracks": item.get("total_tracks"),
                })

            spotify_ids  = [a["spotify_id"] for a in albums]
            local_albums = Album.query.filter(
                Album.spotify_id.in_(spotify_ids)
            ).all()
            local_by_sid = {a.spotify_id: a for a in local_albums}
            ratings      = get_user_ratings(current_user.id)

            for album in albums:
                local = local_by_sid.get(album["spotify_id"])
                album["local_id"]    = local.id if local else None
                album["user_rating"] = ratings.get(local.id) if local else None

            return render_template("artist.html", artist=artist, albums=albums)

        except Exception as e:
            flash(f"Could not load artist page: {e}", "danger")
            return redirect(url_for("dashboard"))

    return app


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)