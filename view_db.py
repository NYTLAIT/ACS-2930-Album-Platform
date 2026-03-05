from ecouter import create_app
from models import User, Album, Playlist

app = create_app()

with app.app_context():
    # View all users
    users = User.query.all()
    for u in users:
        print(u.id, u.username, u.email)
    
    # View all albums
    albums = Album.query.all()
    for a in albums:
        print(a.id, a.name, a.artist)
    
    # View all playlists
    playlists = Playlist.query.all()
    for p in playlists:
        print(p.id, p.name, p.user_id)

# Also can just check it in application DB Browser for SQLite