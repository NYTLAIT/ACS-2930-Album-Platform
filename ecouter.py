# ecouter.py - Main Flask application for Album Platform
# Integrates Spotify API for album and playlist management

import os
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv
from models import user_album

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

from config import DevelopmentConfig
from models import db, init_db, User, Album, Playlist, Artist, user_album, Review
from models.user_album import UserAlbum
from models.comment import AlbumComment
from forms import SignupForm, LoginForm

# Load environment variables
load_dotenv()

def create_app(config_class=DevelopmentConfig): # Check config classes in config.py
    """Create and configure the Flask application"""

# =======================================================================================================================    
# === Initializing ===                                                                                                  =
# ======================================================================================================================= 
    # Initialize app and connect to specified database
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize the database via database.py
    init_db(app)
    
    # Initialize login manager (CHRISTIAN'S DOMAIN)
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Initialize Spotify API (DO NOT TOUCH)
    client_id = os.getenv('CLIENT_ID')
    client_secret = os.getenv('CLIENT_SECRET')
    auth_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
    app.spotify = spotipy.Spotify(auth_manager=auth_manager)

# =======================================================================================================================    
# === Routes ===                                                                                                        =
# ======================================================================================================================= 

    # -------------------------------------------------------------------------------------------------------------------
    # SIGNUP, LOGIN, and LOGOUT
    @app.route('/')
    def index():
        """Landing page"""
        if current_user.is_authenticated:
            return redirect(url_for('home'))
        return render_template('landing.html')
    
    @app.route('/signup', methods=['GET', 'POST'])
    def signup():
        """User signup route"""
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        
        form = SignupForm()
        if form.validate_on_submit():
            # Check if user already exists
            if User.query.filter_by(email=form.email.data).first():
                flash('Email already registered.', 'danger')
                return redirect(url_for('signup'))
                
            if User.query.filter_by(username=form.username.data).first():
                flash('Username already taken.', 'danger')
                return redirect(url_for('signup'))
                
            # Create new user
            user = User(email=form.email.data, username=form.username.data)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
                
            flash('Account created successfully! You can now log in.', 'success')
            return redirect(url_for('login'))
        
        return render_template('signup.html', form=form)
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """User login route"""
        if current_user.is_authenticated:
            return redirect(url_for('home'))
        
        form = LoginForm()

        print("FORM VALID:", form.validate_on_submit())
        print("FORM ERRORS:", form.errors)

        if form.validate_on_submit():
            user = User.query.filter_by(email=form.email.data).first()
            print("FOUND USER:", user)

            if user:
                print("PASSWORD CHECK:", user.check_password(form.password.data))

            if user and user.check_password(form.password.data):
                login_user(user)
                flash('Logged in successfully!', 'success')
                return redirect(url_for('home'))
            else:
                flash('Invalid email or password.', 'danger')
        
        return render_template('login.html', form=form)
    
    @app.route('/logout')
    @login_required
    def logout():
        """Logout user"""
        logout_user()
        flash('Logged out.', 'info')
        return redirect(url_for('login'))
    
    # END SIGNUP, LOGIN, and LOGOUT
    # -------------------------------------------------------------------------------------------------------------------
    
    @app.route('/dashboard')
    @login_required
    def dashboard():
       """Redirect dashboard to home"""
       return redirect(url_for('home'))
    
    @app.route('/playlists')
    @login_required
    def playlists():
        """User playlists page"""
        user_playlists = Playlist.query.filter_by(user_id=current_user.id).all()
        return render_template('playlists.html', playlists=user_playlists)
    
    @app.route('/playlist/<int:playlist_id>')
    @login_required
    def view_playlist(playlist_id):
        playlist = Playlist.query.get_or_404(playlist_id)
        if playlist.user_id != current_user.id:
            flash("Access denied.", "danger")
            return redirect(url_for('playlists'))
        return render_template('view_playlist.html', playlist=playlist)
    
    @app.route('/create_playlist', methods=['GET', 'POST'])
    @login_required
    def create_playlist():
        if request.method == 'POST':
            name = request.form.get('name')
            playlist = Playlist(name=name, user_id=current_user.id)
            db.session.add(playlist)
            db.session.commit()
            flash('Playlist created!', 'success')
            return redirect(url_for('playlists'))
        return render_template('create_playlist.html')

    # Add to Collection (legacy endpoint used by search_results.html)
    @app.route('/add_to_collection/<album_id>', methods=['POST'])
    @login_required
    def add_to_collection(album_id):
        album = Album.query.filter_by(spotify_id=album_id).first()
        if not album:
            flash("Album not found.", "danger")
            return redirect(url_for('home'))

        existing = UserAlbum.query.filter_by(user_id=current_user.id, album_id=album.id).first()
        if existing:
            flash(f"{album.name} is already in your collection.", "info")
        else:
            user_album = UserAlbum(user_id=current_user.id, album_id=album.id)
            db.session.add(user_album)
            db.session.commit()
            flash(f"Added {album.name} to your collection!", "success")

        return redirect(request.referrer or url_for('home'))

    @app.route('/album/<album_id>')
    @login_required
    def album_detail(album_id):
        """Album details page with basic rating sidebar and comments."""
        # Find album by Spotify ID in local DB first
        album = Album.query.filter_by(spotify_id=album_id).first()

        # If not found locally, try to fetch from Spotify and persist
        if not album:
            try:
                spotify_album = app.spotify.album(album_id)
            except Exception:
                flash('Album not found.', 'danger')
                return redirect(request.referrer or url_for('home'))

            # Create or fetch artist
            artist_data = spotify_album['artists'][0] if spotify_album.get('artists') else None
            artist_obj = None
            if artist_data:
                artist_obj = Artist.query.filter_by(spotify_id=artist_data['id']).first()
                if not artist_obj:
                    artist_obj = Artist(
                        spotify_id=artist_data['id'],
                        name=artist_data['name'],
                        image_url=None,
                    )
                    db.session.add(artist_obj)

            album = Album(
                spotify_id=spotify_album['id'],
                name=spotify_album['name'],
                artist=artist_data['name'] if artist_data else 'Unknown',
                artist_id=artist_obj.id if artist_obj else None,
                release_date=spotify_album.get('release_date', ''),
                image_url=spotify_album['images'][0]['url'] if spotify_album.get('images') else None,
                spotify_url=spotify_album.get('external_urls', {}).get('spotify', ''),
                description=spotify_album.get('label', None),
                genres=','.join(spotify_album.get('genres', [])) if spotify_album.get('genres') else None,
            )
            db.session.add(album)
            db.session.commit()

        # User-specific rating (via UserAlbum)
        user_album = UserAlbum.query.filter_by(user_id=current_user.id, album_id=album.id).first()
        user_rating = user_album.rating if user_album and user_album.rating is not None else None

        # Aggregate rating across all users
        from sqlalchemy import func
        avg_rating = db.session.query(func.avg(UserAlbum.rating)).filter(UserAlbum.album_id == album.id, UserAlbum.rating != None).scalar()
        ratings_count = db.session.query(func.count(UserAlbum.id)).filter(UserAlbum.album_id == album.id, UserAlbum.rating != None).scalar()

        # Basic (non-threaded) comments for now: top-level only
        comments = AlbumComment.query.filter_by(album_id=album.id, parent_id=None).order_by(AlbumComment.created_at.desc()).all()

        return render_template(
            'album_detail.html',
            album=album,
            user_rating=user_rating,
            avg_rating=avg_rating,
            ratings_count=ratings_count,
            comments=comments,
        )
    
    @app.route('/add_to_playlist', methods=['POST'])
    @login_required
    def add_to_playlist():
        spotify_id = request.form.get('spotify_id')
        name = request.form.get('name')
        artist = request.form.get('artist')
        release_date = request.form.get('release_date')
        image_url = request.form.get('image_url')
        playlist_id = request.form.get('playlist_id')

        playlist = Playlist.query.get_or_404(playlist_id)

        if playlist.user_id != current_user.id:
            flash("Unauthorized.", "danger")
            return redirect(url_for('home'))

        # Check if album already exists in DB
        album = Album.query.filter_by(spotify_id=spotify_id).first()

        if not album:
            album = Album(
                spotify_id=spotify_id,
                name=name,
                artist=artist,
                release_date=release_date,
                image_url=image_url
           )
            db.session.add(album)
            db.session.commit()

        if album not in playlist.albums:
            playlist.albums.append(album)
            db.session.commit()
            flash("✅ Added to playlist!", "success")
        else:
            flash("Already in this playlist.", "info")

        return redirect(request.referrer or url_for('home'))

    @app.route('/album/<album_id>/comment', methods=['POST'])
    @login_required
    def add_album_comment(album_id):
        """Add a top-level comment to an album."""
        album = Album.query.filter_by(spotify_id=album_id).first()
        if not album:
            flash('Album not found.', 'danger')
            return redirect(request.referrer or url_for('home'))

        body = request.form.get('body', '').strip()
        if not body:
            flash('Comment cannot be empty.', 'danger')
            return redirect(url_for('album_detail', album_id=album_id))

        comment = AlbumComment(album_id=album.id, user_id=current_user.id, body=body)
        db.session.add(comment)
        db.session.commit()

        flash('Comment added.', 'success')
        return redirect(url_for('album_detail', album_id=album_id))

    @app.route('/edit_playlist/<int:playlist_id>', methods=['POST'])
    @login_required
    def edit_playlist(playlist_id):
        playlist = Playlist.query.get_or_404(playlist_id)

        if playlist.user_id != current_user.id:
            flash("Unauthorized.", "danger")
            return redirect(url_for('playlists'))

        new_name = request.form.get('name')
        if new_name:
            playlist.name = new_name
            db.session.commit()
            flash("Playlist updated!", "success")

        return redirect(url_for('playlists'))


    @app.route('/rate_album/<album_id>', methods=['POST'])
    @login_required
    def rate_album(album_id):
        """Rate an album by its Spotify ID using UserAlbum as storage."""
        album = Album.query.filter_by(spotify_id=album_id).first_or_404()
        rating = request.form.get('rating', type=float)
        if not rating or rating < 0.5 or rating > 5:
            flash("Invalid rating value.", "danger")
            return redirect(request.referrer or url_for('home'))

        existing = UserAlbum.query.filter_by(user_id=current_user.id, album_id=album.id).first()
        if existing:
            existing.rating = rating
            db.session.commit()
            flash(f"Updated rating for {album.name} to {rating} stars.", "success")
        else:
            flash(f"Add {album.name} to your collection first.", "danger")

        return redirect(request.referrer or url_for('home'))
    
    # /home route — acts as dashboard + home
    @app.route('/home')
    @login_required
    def home():
        """Home page / user dashboard"""
        # Get all playlists for current user
        playlists = Playlist.query.filter_by(user_id=current_user.id).all()

        # Precompute ratings for current user's albums
        ratings = {}
        for playlist in playlists:
            for album in playlist.albums:
                for r in album.user_ratings:  # r is a User
                    if r.id == current_user.id:
                        # Find rating in UserAlbum
                        user_album = next((ua for ua in r.user_albums if ua.album_id == album.id), None)
                        if user_album:
                            ratings[album.id] = user_album.rating

        return render_template('home.html', playlists=playlists, ratings=ratings)
    
    # -------------------------------------------------------------------------------------------------------------------
    # SEARCH ROUTE
    @app.route('/search')
    @login_required
    def search():
        """Search for albums"""
        query = request.args.get('query', '').strip()
        albums = []
        
        if query:
            try:
                # Search using Spotify API with proper parameters
                results = app.spotify.search(q=query, type='album', limit=10, offset=0)
                
                for item in results.get('albums', {}).get('items', []):
                    album = {
                        'name': item.get('name', 'Unknown'),
                        'artist': ', '.join([artist['name'] for artist in item.get('artists', [])]),
                        'release_date': item.get('release_date', ''),
                        'album_art': item['images'][0]['url'] if item.get('images') else None,
                        'spotify_id': item.get('id', ''),
                    }
                    albums.append(album)
            except Exception as e:
                flash(f'Error searching albums: {str(e)}', 'danger')
        
        return render_template('search_results.html', albums=albums, query=query)
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
