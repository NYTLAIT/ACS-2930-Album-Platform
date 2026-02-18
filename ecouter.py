# Client Credentials Flow (no access to spotify accounts (cant access, modify, see user playlists or control playback))
# Authorization Code Flow (Search artists, get track info, album data, and audio features)
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

from forms import SignupForm, LoginForm

from flask import Flask, render_template, request, redirect, url_for, flash
app = Flask(__name__)
app.config['SECRET_KEY'] = 'something_idk'

import os
from dotenv import load_dotenv
load_dotenv()

client_id = os.getenv('CLIENT_ID')
client_secret = os.getenv('CLIENT_SECRET')

auth_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
spotipy_bot = spotipy.Spotify(auth_manager=auth_manager)

users = {}

@app.route('/')
def index():
    # Send users to the login page first
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    form = SignupForm()
    if form.validate_on_submit():
        email = form.email.data.lower()
        if email in users:
            flash('Email is already registered. Please log in instead.', 'error')
        else:
            users[email] = {
                'username': form.username.data,
                'password': form.password.data,
            }
            flash('Account created successfully! You can now log in.', 'success')
            return redirect(url_for('login'))
    return render_template('signup.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.lower()
        password = form.password.data
        user = users.get(email)
        if not user or user['password'] != password:
            flash('Invalid email or password.', 'error')
        else:
            flash(f"Welcome back, {user['username']}!", 'success')
            return redirect(url_for('login'))
    return render_template('login.html', form=form)

if __name__ == '__main__':
    app.run(debug=True)