# Always run ecouter.py unless need to reset db or some
from ecouter import create_app, db
from models import Album, User

app = create_app()
with app.app_context():
    db.create_all()
    
    # Example albums
    if not Album.query.first():
        a1 = Album(name="Discovery", artist="Daft Punk", spotify_id="abc123")
        a2 = Album(name="Abbey Road", artist="The Beatles", spotify_id="def456")
        db.session.add_all([a1, a2])
        db.session.commit()
        print("Seeded DB!")