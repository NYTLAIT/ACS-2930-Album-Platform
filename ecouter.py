# ecouter.py
# This is the main application file. It creates the Flask app and defines
# every route. A route is a function that runs when a user visits a URL.
#
# All routes are defined inside create_app() so they have access to the
# app, database, and Spotify client.

import os
import json

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv

from flask import (
    Flask, render_template, request,
    redirect, url_for, flash, jsonify
)
from flask_login import (
    LoginManager, login_user, logout_user,
    login_required, current_user
)
from flask_migrate import Migrate

from config import DevelopmentConfig
from models import (
    db, init_db,
    User, Album, Collection, collection_albums,
    UserAlbum, RATING_LIKE, RATING_DISLIKE,
    MoodTag, AlbumMood, seed_mood_tags,
    Comment, CommentVote
)
from forms import SignupForm, LoginForm

# Load environment variables from .env file
# This reads CLIENT_ID, CLIENT_SECRET, SECRET_KEY etc.
load_dotenv()


# ---------------------------------------------------------------------------
# Helper functions
# Small utilities used by multiple routes.
# ---------------------------------------------------------------------------

def ms_to_duration(ms):
    """Convert milliseconds to a readable string like '4:32'."""
    if not ms:
        return '0:00'
    seconds = ms // 1000
    minutes = seconds // 60
    seconds = seconds % 60
    return f'{minutes}:{seconds:02d}'


def get_user_ratings(user_id):
    """
    Return a dictionary of { album_id: rating } for a given user.
    Fetches all ratings in one query so routes do not query per album.
    """
    rows = UserAlbum.query.filter_by(user_id=user_id).all()
    return {row.album_id: row.rating for row in rows}


def get_user_moods(user_id, album_id):
    """
    Return a list of mood_tag_ids the user has applied to a specific album.
    """
    rows = AlbumMood.query.filter_by(
        user_id=user_id,
        album_id=album_id
    ).all()
    return [row.mood_tag_id for row in rows]


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app(config_class=DevelopmentConfig):
    """Create and configure the Flask application."""

    app = Flask(__name__)
    app.config.from_object(config_class)

    # Connect the database to the app and create any missing tables
    init_db(app)

    # Flask-Migrate tracks model changes so the database can be updated
    # without losing data. Run 'flask db migrate' then 'flask db upgrade'
    # after changing any model.
    migrate = Migrate(app, db)

    # Seed the mood tags once at startup (safe to call repeatedly)
    with app.app_context():
        seed_mood_tags()

    # -------------------------------------------------------------------
    # Flask-Login setup
    # Handles sessions — remembers who is logged in across requests.
    # -------------------------------------------------------------------
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'  # redirect here if not logged in

    @login_manager.user_loader
    def load_user(user_id):
        """Tell Flask-Login how to find a user by their session ID."""
        return User.query.get(int(user_id))

    # -------------------------------------------------------------------
    # Spotify API setup
    # Attached to app so all routes can use it via app.spotify
    # -------------------------------------------------------------------
    client_id     = os.getenv('CLIENT_ID')
    client_secret = os.getenv('CLIENT_SECRET')
    auth_manager  = SpotifyClientCredentials(
        client_id=client_id,
        client_secret=client_secret
    )
    app.spotify = spotipy.Spotify(auth_manager=auth_manager)

    # ===================================================================
    # AUTH ROUTES
    # Public routes — no @login_required.
    # ===================================================================

    @app.route('/')
    def index():
        """Landing page. Redirect to dashboard if already logged in."""
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        return render_template('landing.html')

    @app.route('/signup', methods=['GET', 'POST'])
    def signup():
        """Show the signup form (GET) or create a new account (POST)."""
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))

        form = SignupForm()

        if form.validate_on_submit():
            if User.query.filter_by(email=form.email.data).first():
                flash('That email is already registered.', 'danger')
                return redirect(url_for('signup'))

            if User.query.filter_by(username=form.username.data).first():
                flash('That username is already taken.', 'danger')
                return redirect(url_for('signup'))

            user = User(
                email=form.email.data,
                username=form.username.data
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()

            flash('Account created. You can now log in.', 'success')
            return redirect(url_for('login'))

        return render_template('signup.html', form=form)

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """Show the login form (GET) or log the user in (POST)."""
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))

        form = LoginForm()

        if form.validate_on_submit():
            user = User.query.filter_by(email=form.email.data).first()
            if user and user.check_password(form.password.data):
                login_user(user)
                flash('Logged in successfully.', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Incorrect email or password.', 'danger')

        return render_template('login.html', form=form)

    @app.route('/logout')
    @login_required
    def logout():
        """Log the user out and send them to the login page."""
        logout_user()
        flash('You have been logged out.', 'info')
        return redirect(url_for('login'))

    # ===================================================================
    # DASHBOARD — Discovery hub
    # Shows recent activity, trending, top rated, new arrivals,
    # unrated albums from public collections, and the user's collections.
    # Can be filtered by mood tags.
    # ===================================================================

    @app.route('/dashboard')
    @login_required
    def dashboard():
        """
        Main dashboard — doubles as the discovery page.

        Query parameters:
            moods     — comma-separated mood_tag_ids to filter by
            mood_mode — 'any' (default) or 'all'
        """
        from sqlalchemy import func
        from datetime import datetime as _dt3, timedelta

        # --- Mood filter ---
        mood_param      = request.args.get('moods', '').strip()
        mood_mode       = request.args.get('mood_mode', 'any')
        active_mood_ids = []

        if mood_param:
            try:
                active_mood_ids = [int(x) for x in mood_param.split(',') if x.strip()]
            except ValueError:
                active_mood_ids = []

        # --- Album IDs in at least one public collection ---
        from models import collection_albums as ca_table

        public_id_rows = db.session.query(ca_table.c.album_id).join(
            Collection, Collection.id == ca_table.c.collection_id
        ).filter(Collection.is_public == True).distinct().all()

        public_album_ids = [row[0] for row in public_id_rows]

        # --- Apply mood filter to a list of album IDs ---
        def apply_mood_filter(base_ids):
            if not active_mood_ids or not base_ids:
                return base_ids
            if mood_mode == 'all':
                rows = db.session.query(AlbumMood.album_id).filter(
                    AlbumMood.album_id.in_(base_ids),
                    AlbumMood.mood_tag_id.in_(active_mood_ids)
                ).group_by(AlbumMood.album_id).having(
                    func.count(func.distinct(AlbumMood.mood_tag_id)) == len(active_mood_ids)
                ).all()
            else:
                rows = db.session.query(AlbumMood.album_id).filter(
                    AlbumMood.album_id.in_(base_ids),
                    AlbumMood.mood_tag_id.in_(active_mood_ids)
                ).distinct().all()
            return [r[0] for r in rows]

        filtered_ids = apply_mood_filter(public_album_ids)

        # --- Section: Recently viewed albums (last 6 the user visited) ---
        recent_view_rows = UserAlbum.query.filter(
            UserAlbum.user_id == current_user.id,
            UserAlbum.last_viewed_at != None
        ).order_by(UserAlbum.last_viewed_at.desc()).limit(6).all()

        recently_viewed = [row.album for row in recent_view_rows]

        # --- Section: Recently interacted collections ---
        # Collections the user has opened or had albums added to recently
        recent_cols = Collection.query.filter(
            Collection.user_id == current_user.id,
            Collection.last_opened_at != None
        ).order_by(Collection.last_opened_at.desc()).limit(4).all()

        # Fall back to most recently created if none opened yet
        if not recent_cols:
            recent_cols = Collection.query.filter_by(
                user_id=current_user.id
            ).order_by(Collection.created_at.desc()).limit(4).all()

        # --- Section: Trending this week ---
        one_week_ago = _dt3.utcnow() - timedelta(days=7)

        trending_rows = db.session.query(
            Album, func.count(UserAlbum.id).label('like_count')
        ).join(UserAlbum, UserAlbum.album_id == Album.id).filter(
            Album.id.in_(filtered_ids) if filtered_ids else False,
            UserAlbum.rating == 1,
            UserAlbum.updated_at >= one_week_ago
        ).group_by(Album.id).order_by(
            func.count(UserAlbum.id).desc()
        ).limit(12).all()

        trending = [{'album': r[0], 'like_count': r[1]} for r in trending_rows]

        # --- Section: Top rated overall ---
        top_rows = db.session.query(
            Album, func.count(UserAlbum.id).label('like_count')
        ).join(UserAlbum, UserAlbum.album_id == Album.id).filter(
            Album.id.in_(filtered_ids) if filtered_ids else False,
            UserAlbum.rating == 1
        ).group_by(Album.id).order_by(
            func.count(UserAlbum.id).desc()
        ).limit(12).all()

        top_rated = [{'album': r[0], 'like_count': r[1]} for r in top_rows]

        # --- Section: New arrivals ---
        new_rows = Album.query.filter(
            Album.id.in_(filtered_ids) if filtered_ids else False
        ).order_by(Album.id.desc()).limit(12).all()

        new_arrivals = new_rows

        # --- Section: Unrated by you ---
        rated_by_me = db.session.query(UserAlbum.album_id).filter(
            UserAlbum.user_id == current_user.id,
            UserAlbum.rating != None
        ).subquery()

        unrated_rows = db.session.query(
            Album, func.count(UserAlbum.id).label('like_count')
        ).join(UserAlbum, UserAlbum.album_id == Album.id).filter(
            Album.id.in_(filtered_ids) if filtered_ids else False,
            UserAlbum.rating == 1,
            Album.id.notin_(rated_by_me)
        ).group_by(Album.id).order_by(
            func.count(UserAlbum.id).desc()
        ).limit(12).all()

        unrated = [{'album': r[0], 'like_count': r[1]} for r in unrated_rows]

        # --- User's own collections ---
        my_collections = Collection.query.filter_by(
            user_id=current_user.id
        ).order_by(Collection.created_at.desc()).all()

        ratings        = get_user_ratings(current_user.id)
        all_mood_tags  = MoodTag.query.order_by(MoodTag.category, MoodTag.name).all()

        return render_template(
            'dashboard.html',
            recently_viewed=recently_viewed,
            recent_collections=recent_cols,
            trending=trending,
            top_rated=top_rated,
            new_arrivals=new_arrivals,
            unrated=unrated,
            collections=my_collections,
            ratings=ratings,
            all_mood_tags=all_mood_tags,
            active_mood_ids=active_mood_ids,
            mood_mode=mood_mode,
            no_public_albums=(len(public_album_ids) == 0)
        )

    # Keep /home working as a redirect so old links do not break
    @app.route('/home')
    @login_required
    def home():
        return redirect(url_for('dashboard'))

    # ===================================================================
    # COLLECTIONS
    # ===================================================================

    @app.route('/collections')
    @login_required
    def collections():
        """List all of the current user's collections."""
        user_collections = Collection.query.filter_by(
            user_id=current_user.id
        ).order_by(Collection.created_at.desc()).all()

        return render_template('collections.html', collections=user_collections)

    # Keep /playlists working as a redirect
    @app.route('/playlists')
    @login_required
    def playlists():
        return redirect(url_for('collections'))

    @app.route('/collection/<int:playlist_id>')
    @login_required
    def view_collection(playlist_id):
        """
        View a single collection and its albums.
        Private collections can only be viewed by their owner.
        Public collections are visible to any logged-in user.
        """
        from datetime import datetime as _dt
        collection = Collection.query.get_or_404(playlist_id)

        if not collection.is_public and collection.user_id != current_user.id:
            flash('That collection is private.', 'danger')
            return redirect(url_for('collections'))

        # Stamp last_opened_at so the dashboard shows recently opened collections
        if collection.user_id == current_user.id:
            collection.last_opened_at = _dt.utcnow()
            db.session.commit()

        ratings = get_user_ratings(current_user.id)

        return render_template(
            'view_collection.html',
            collection=collection,
            ratings=ratings,
            is_owner=(collection.user_id == current_user.id)
        )

    @app.route('/create_collection', methods=['GET', 'POST'])
    @login_required
    def create_collection():
        """
        Show the create form (GET) or save a new collection (POST).
        When called via JavaScript (AJAX), returns JSON instead of redirecting.
        This allows the search page modal to create collections inline.
        """
        if request.method == 'POST':
            name        = request.form.get('name', '').strip()
            description = request.form.get('description', '').strip()
            is_public   = request.form.get('is_public') == 'true'

            if not name:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'error': 'Name is required'}), 400
                flash('Please enter a collection name.', 'danger')
                return redirect(url_for('create_collection'))

            new_collection = Collection(
                name=name,
                description=description or None,
                is_public=is_public,
                user_id=current_user.id
            )
            db.session.add(new_collection)
            db.session.commit()

            # AJAX call from the search modal — return JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'id':   new_collection.id,
                    'name': new_collection.name
                })

            flash('Collection created.', 'success')
            return redirect(url_for('collections'))

        return render_template('create_collection.html')

    @app.route('/edit_collection/<int:playlist_id>', methods=['POST'])
    @login_required
    def edit_collection(playlist_id):
        """Update a collection's name, description, or public/private setting."""
        collection = Collection.query.get_or_404(playlist_id)

        if collection.user_id != current_user.id:
            flash('You do not have permission to edit that collection.', 'danger')
            return redirect(url_for('collections'))

        name        = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        is_public   = request.form.get('is_public') == 'on'

        if name:
            collection.name = name
        collection.description = description or None
        collection.is_public   = is_public

        db.session.commit()
        flash('Collection updated.', 'success')
        return redirect(url_for('view_collection', playlist_id=collection.id))

    @app.route('/delete_collection/<int:playlist_id>', methods=['POST'])
    @login_required
    def delete_collection(playlist_id):
        """Permanently delete a collection. Only the owner can do this."""
        collection = Collection.query.get_or_404(playlist_id)

        if collection.user_id != current_user.id:
            flash('You do not have permission to delete that collection.', 'danger')
            return redirect(url_for('collections'))

        db.session.delete(collection)
        db.session.commit()
        flash('Collection deleted.', 'success')
        return redirect(url_for('collections'))

    # ===================================================================
    # ADD TO COLLECTION
    # Called from the search page via JavaScript (AJAX).
    # ===================================================================

    @app.route('/add_to_collection', methods=['POST'])
    @login_required
    def add_to_collection():
        """
        Add an album to one of the current user's collections.
        If the album is not in our database yet, it is created here.
        Returns JSON so JavaScript can update the page without reloading.
        """
        spotify_id    = request.form.get('spotify_id')
        name          = request.form.get('name')
        artist        = request.form.get('artist')
        artist_id     = request.form.get('artist_id', '')
        release_date  = request.form.get('release_date', '')
        image_url     = request.form.get('image_url', '')
        playlist_id = request.form.get('playlist_id')

        if not spotify_id or not playlist_id:
            return jsonify({'error': 'Missing data'}), 400

        collection = Collection.query.get_or_404(playlist_id)
        if collection.user_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403

        # Find or create the album row in our database
        album = Album.query.filter_by(spotify_id=spotify_id).first()
        if not album:
            album = Album(
                spotify_id=spotify_id,
                name=name,
                artist=artist,
                artist_id=artist_id,
                release_date=release_date,
                image_url=image_url
                # tracklist is fetched lazily on first visit to album_detail
            )
            db.session.add(album)
            db.session.commit()

        if album not in collection.albums:
            collection.albums.append(album)
            db.session.commit()
            return jsonify({
                'status':  'added',
                'message': f'Added to {collection.name}'
            })

        return jsonify({
            'status':  'exists',
            'message': 'Already in this collection'
        })

    # ===================================================================
    # RATINGS
    # Like or Dislike. One rating per user per album. Togglable.
    # ===================================================================

    @app.route('/rate_album', methods=['POST'])
    @login_required
    def rate_album():
        """
        Save, update, or remove a Like/Dislike rating.
        Clicking the same button twice removes the rating (toggle).
        Clicking the opposite button switches the rating.
        Returns JSON — the page updates without reloading.
        """
        album_id = request.form.get('album_id')
        rating   = request.form.get('rating')

        if not album_id or rating not in ('1', '-1'):
            return jsonify({'error': 'Invalid data'}), 400

        rating = int(rating)
        album  = Album.query.get_or_404(int(album_id))

        entry = UserAlbum.query.filter_by(
            user_id=current_user.id,
            album_id=album.id
        ).first()

        if entry:
            if entry.rating == rating:
                # Same button — toggle off
                entry.rating = None
                db.session.commit()
                return jsonify({'status': 'removed', 'rating': None})
            else:
                # Different button — switch
                entry.rating = rating
                db.session.commit()
                return jsonify({'status': 'updated', 'rating': rating})
        else:
            # No entry yet — create one
            entry = UserAlbum(
                user_id=current_user.id,
                album_id=album.id,
                rating=rating
            )
            db.session.add(entry)
            db.session.commit()
            return jsonify({'status': 'added', 'rating': rating})

    # ===================================================================
    # NOTES
    # Private per-user note on an album.
    # ===================================================================

    @app.route('/save_note', methods=['POST'])
    @login_required
    def save_note():
        """
        Save or update the current user's private note on an album.
        Creates a UserAlbum row if one does not already exist.
        """
        album_id = request.form.get('album_id')
        notes    = request.form.get('notes', '').strip()

        album = Album.query.get_or_404(int(album_id))

        entry = UserAlbum.query.filter_by(
            user_id=current_user.id,
            album_id=album.id
        ).first()

        if entry:
            entry.notes = notes or None
        else:
            entry = UserAlbum(
                user_id=current_user.id,
                album_id=album.id,
                notes=notes or None
            )
            db.session.add(entry)

        db.session.commit()
        return jsonify({'status': 'ok'})

    # ===================================================================
    # MOOD TAGS
    # Public tags that aggregate across all users on the album page.
    # Max 3 per user per album.
    # ===================================================================

    @app.route('/tag_mood', methods=['POST'])
    @login_required
    def tag_mood():
        """
        Toggle a mood tag on an album for the current user.
        If not applied: add it (unless the 3-tag limit is reached).
        If already applied: remove it.
        Returns JSON.
        """
        album_id    = request.form.get('album_id')
        mood_tag_id = request.form.get('mood_tag_id')

        if not album_id or not mood_tag_id:
            return jsonify({'error': 'Missing data'}), 400

        album    = Album.query.get_or_404(int(album_id))
        mood_tag = MoodTag.query.get_or_404(int(mood_tag_id))

        # Check if this tag is already applied by this user
        existing = AlbumMood.query.filter_by(
            user_id=current_user.id,
            album_id=album.id,
            mood_tag_id=mood_tag.id
        ).first()

        if existing:
            # Already applied — remove it
            db.session.delete(existing)
            db.session.commit()
            return jsonify({'status': 'removed', 'tag_id': mood_tag.id})

        # Not applied — check the 3-tag limit
        current_count = AlbumMood.query.filter_by(
            user_id=current_user.id,
            album_id=album.id
        ).count()

        if current_count >= 3:
            return jsonify({
                'status':  'limit_reached',
                'message': 'You can only apply 3 mood tags per album'
            }), 400

        new_mood = AlbumMood(
            user_id=current_user.id,
            album_id=album.id,
            mood_tag_id=mood_tag.id
        )
        db.session.add(new_mood)
        db.session.commit()
        return jsonify({'status': 'added', 'tag_id': mood_tag.id})

    # ===================================================================
    # ALBUM DETAIL
    # Full album page: tracklist, ratings panel, moods, comments.
    # ===================================================================

    @app.route('/album/<int:album_id>')
    @login_required
    def album_detail(album_id):
        """
        Album detail page.
        Tracklist data is fetched from Spotify on first visit and then
        saved to the database so subsequent visits are fast.
        """
        from sqlalchemy import func

        album = Album.query.get_or_404(album_id)

        # Fetch and save full album data from Spotify if we do not have it yet
        if not album.tracklist:
            try:
                full = app.spotify.album(album.spotify_id)

                tracks = []
                for track in full['tracks']['items']:
                    tracks.append({
                        'name':         track['name'],
                        'duration_ms':  track['duration_ms'],
                        'track_number': track['track_number']
                    })

                album.tracklist    = json.dumps(tracks)
                album.total_tracks = full.get('total_tracks')
                album.duration_ms  = sum(
                    t['duration_ms'] for t in full['tracks']['items']
                )

                if not album.artist_id and full.get('artists'):
                    album.artist_id = full['artists'][0]['id']

                db.session.commit()

            except Exception:
                # If Spotify call fails, continue with no tracklist
                pass

        # Stamp last_viewed_at on the UserAlbum row (create one if needed)
        from datetime import datetime as _dt2
        ua_stamp = UserAlbum.query.filter_by(
            user_id=current_user.id,
            album_id=album.id
        ).first()
        if ua_stamp:
            ua_stamp.last_viewed_at = _dt2.utcnow()
        else:
            ua_stamp = UserAlbum(
                user_id=current_user.id,
                album_id=album.id,
                last_viewed_at=_dt2.utcnow()
            )
            db.session.add(ua_stamp)
        db.session.commit()

        # Parse tracklist and add formatted duration to each track
        tracks = json.loads(album.tracklist) if album.tracklist else []
        for track in tracks:
            track['duration'] = ms_to_duration(track.get('duration_ms', 0))

        # Current user's rating and notes
        user_album_entry = UserAlbum.query.filter_by(
            user_id=current_user.id,
            album_id=album.id
        ).first()

        user_rating = user_album_entry.rating if user_album_entry else None
        user_notes  = user_album_entry.notes  if user_album_entry else None

        # Total likes and dislikes across all users
        all_entries    = UserAlbum.query.filter_by(album_id=album.id).all()
        total_likes    = sum(1 for e in all_entries if e.rating == RATING_LIKE)
        total_dislikes = sum(1 for e in all_entries if e.rating == RATING_DISLIKE)

        # Mood counts: how many users applied each tag
        # Returns list of (MoodTag, count) ordered by count descending
        mood_counts = db.session.query(
            MoodTag,
            func.count(AlbumMood.id).label('count')
        ).join(
            AlbumMood, MoodTag.id == AlbumMood.mood_tag_id
        ).filter(
            AlbumMood.album_id == album.id
        ).group_by(
            MoodTag.id
        ).order_by(
            func.count(AlbumMood.id).desc()
        ).all()

        # Which moods has the current user applied to this album
        user_mood_ids = get_user_moods(current_user.id, album.id)

        # All mood tags grouped by category for the tag picker
        all_mood_tags = MoodTag.query.order_by(
            MoodTag.category, MoodTag.name
        ).all()
        moods_by_category = {}
        for tag in all_mood_tags:
            moods_by_category.setdefault(tag.category, []).append(tag)

        # Top-level comments — replies load through comment.replies
        comments = Comment.query.filter_by(
            album_id=album.id,
            parent_id=None
        ).order_by(Comment.created_at.desc()).all()

        # Current user's votes — dict of comment_id -> vote value
        def collect_comment_ids(comment_list):
            """Recursively collect IDs from comments and all their replies."""
            ids = []
            for c in comment_list:
                ids.append(c.id)
                ids.extend(collect_comment_ids(c.replies))
            return ids

        user_votes = {}
        all_comment_ids = collect_comment_ids(comments)
        if all_comment_ids:
            vote_rows = CommentVote.query.filter(
                CommentVote.user_id == current_user.id,
                CommentVote.comment_id.in_(all_comment_ids)
            ).all()
            user_votes = {v.comment_id: v.value for v in vote_rows}

        return render_template(
            'album_detail.html',
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
            RATING_DISLIKE=RATING_DISLIKE
        )

    # ===================================================================
    # COMMENTS
    # Post a comment or reply. Vote on a comment.
    # ===================================================================

    @app.route('/comment', methods=['POST'])
    @login_required
    def post_comment():
        """
        Post a comment on an album.
        If parent_id is included it is a reply to that comment.
        Redirects back to the album detail page after posting.
        """
        album_id  = request.form.get('album_id')
        content   = request.form.get('content', '').strip()
        parent_id = request.form.get('parent_id') or None

        if not content:
            flash('Comment cannot be empty.', 'danger')
            return redirect(url_for('album_detail', album_id=album_id))

        album = Album.query.get_or_404(int(album_id))

        comment = Comment(
            content=content,
            user_id=current_user.id,
            album_id=album.id,
            parent_id=int(parent_id) if parent_id else None
        )
        db.session.add(comment)
        db.session.commit()

        return redirect(url_for('album_detail', album_id=album.id))

    @app.route('/vote_comment', methods=['POST'])
    @login_required
    def vote_comment():
        """
        Upvote (1) or downvote (-1) a comment.
        Same vote again removes it. Opposite vote switches it.
        Returns JSON with the new score.
        """
        comment_id = request.form.get('comment_id')
        value      = request.form.get('value')

        if not comment_id or value not in ('1', '-1'):
            return jsonify({'error': 'Invalid data'}), 400

        value   = int(value)
        comment = Comment.query.get_or_404(int(comment_id))

        existing = CommentVote.query.filter_by(
            user_id=current_user.id,
            comment_id=comment.id
        ).first()

        if existing:
            if existing.value == value:
                # Same direction — remove the vote
                db.session.delete(existing)
                db.session.commit()
                return jsonify({'status': 'removed', 'score': comment.score})
            else:
                # Opposite direction — switch
                existing.value = value
                db.session.commit()
                return jsonify({'status': 'switched', 'score': comment.score})
        else:
            vote = CommentVote(
                user_id=current_user.id,
                comment_id=comment.id,
                value=value
            )
            db.session.add(vote)
            db.session.commit()
            return jsonify({'status': 'added', 'score': comment.score})

    # ===================================================================
    # ARTIST PAGE
    # Data fetched live from Spotify — no Artist model needed.
    # ===================================================================

    @app.route('/artist/<spotify_artist_id>')
    @login_required
    def artist_page(spotify_artist_id):
        """
        Artist page. Fetches artist info and albums live from Spotify.
        Also checks which albums we have locally so we can show ratings
        and link to the album detail page.
        """
        try:
            artist_data = app.spotify.artist(spotify_artist_id)
            albums_data = app.spotify.artist_albums(
                spotify_artist_id,
                album_type='album',
                limit=20
            )

            # Safely extract each field — Spotify can return missing or
            # differently shaped data depending on the artist
            images         = artist_data.get('images') or []
            followers_data = artist_data.get('followers') or {}
            followers      = followers_data.get('total', 0) if isinstance(followers_data, dict) else 0

            artist = {
                'name':      artist_data.get('name', 'Unknown Artist'),
                'image_url': images[0]['url'] if images else None,
                'followers': followers,
                'genres':    artist_data.get('genres', [])
            }

            albums = []
            for item in albums_data.get('items', []):
                albums.append({
                    'spotify_id':   item['id'],
                    'name':         item['name'],
                    'release_date': item.get('release_date', ''),
                    'image_url':    item['images'][0]['url'] if item['images'] else None,
                    'total_tracks': item.get('total_tracks')
                })

            # Check which of these albums exist in our database
            spotify_ids      = [a['spotify_id'] for a in albums]
            local_albums     = Album.query.filter(
                Album.spotify_id.in_(spotify_ids)
            ).all()
            local_by_sid     = {a.spotify_id: a for a in local_albums}
            ratings          = get_user_ratings(current_user.id)

            for album in albums:
                local = local_by_sid.get(album['spotify_id'])
                album['local_id']    = local.id if local else None
                album['user_rating'] = ratings.get(local.id) if local else None

        except Exception as e:
            flash(f'Could not load artist page: {str(e)}', 'danger')
            return redirect(url_for('dashboard'))

        return render_template('artist.html', artist=artist, albums=albums)

    # ===================================================================
    # SEARCH
    # ===================================================================

    @app.route('/search')
    @login_required
    def search():
        """
        Search Spotify for albums. Results are displayed but not saved.
        Users can add any result to a collection from this page.
        Existing ratings are shown if the album is already in our database.
        """
        query  = request.args.get('query', '').strip()
        albums = []

        if query:
            try:
                results = app.spotify.search(q=query, type='album', limit=12)

                for item in results.get('albums', {}).get('items', []):
                    albums.append({
                        'spotify_id':   item.get('id', ''),
                        'name':         item.get('name', 'Unknown'),
                        'artist':       ', '.join(
                            a['name'] for a in item.get('artists', [])
                        ),
                        'artist_id':    item['artists'][0]['id'] if item.get('artists') else '',
                        'release_date': item.get('release_date', ''),
                        'image_url':    item['images'][0]['url'] if item.get('images') else None,
                    })

            except Exception as e:
                flash(f'Search failed: {str(e)}', 'danger')

        # Collections for the Add to Collection modal
        user_collections = Collection.query.filter_by(
            user_id=current_user.id
        ).all()

        # Ratings for albums already in our database
        ratings = get_user_ratings(current_user.id)

        # Attach local database info to each search result
        if albums:
            spotify_ids  = [a['spotify_id'] for a in albums]
            local_albums = Album.query.filter(
                Album.spotify_id.in_(spotify_ids)
            ).all()
            local_by_sid = {a.spotify_id: a for a in local_albums}

            for album in albums:
                local = local_by_sid.get(album['spotify_id'])
                album['local_id']    = local.id if local else None
                album['user_rating'] = ratings.get(local.id) if local else None

        return render_template(
            'search_results.html',
            albums=albums,
            query=query,
            collections=user_collections
        )

    return app


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)