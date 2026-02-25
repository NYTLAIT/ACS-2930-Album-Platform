# ecouter.py - Main Flask application for Album Platform
# Integrates Spotify API for album and playlist management

import os
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv

from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

from config import DevelopmentConfig
from models import db, init_db, User, Album, Playlist
from forms import SignupForm, LoginForm

# Load environment variables
load_dotenv()

def create_app(config_class=DevelopmentConfig):
    """Create and configure the Flask application"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    
    # Initialize login manager
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Initialize Spotify API
    client_id = os.getenv('CLIENT_ID')
    client_secret = os.getenv('CLIENT_SECRET')
    auth_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
    app.spotify = spotipy.Spotify(auth_manager=auth_manager)
    
    # Create database tables
    with app.app_context():
        db.create_all()
    
    # === Routes ===
    
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
            try:
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
            except Exception as e:
                db.session.rollback()
                flash(f'Error creating account: {str(e)}', 'danger')
                return redirect(url_for('signup'))
        
        return render_template('signup.html', form=form)
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """User login route"""
        if current_user.is_authenticated:
            return redirect(url_for('home'))
        
        form = LoginForm()
        # TODO: Uncomment form validation and database check when ready
        # if form.validate_on_submit():
        #     user = User.query.filter_by(email=form.email.data).first()
        #     if user is None or not user.check_password(form.password.data):
        #         flash('Invalid email or password.', 'danger')
        #         return redirect(url_for('login'))
        #     login_user(user)
        
        # For now, just skip validation and let user through
        if request.method == 'POST':
            flash('Logged in successfully!', 'success')
            return redirect(url_for('home'))
        
        return render_template('login.html', form=form)
    
    @app.route('/logout')
    # @login_required  # TODO: Uncomment when database auth is ready
    def logout():
        """Logout user"""
        logout_user()
        flash('You have been logged out.', 'info')
        return redirect(url_for('login'))
    
    @app.route('/dashboard')
    # @login_required  # TODO: Uncomment when database auth is ready
    def dashboard():
        """User dashboard"""
        playlists = Playlist.query.filter_by(user_id=current_user.id).all()
        return render_template('dashboard.html', playlists=playlists)
    
    @app.route('/home')
    # @login_required  # TODO: Uncomment when database auth is ready
    def home():
        """Home page with search functionality"""
        return render_template('home.html')
    
    @app.route('/search')
    # @login_required  # TODO: Uncomment when database auth is ready
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
