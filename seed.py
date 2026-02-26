from ecouter import create_app, db
from models import Album, User

app = create_app()

with app.app_context():
    db.create_all()
    
    # Seed Albums
    if not Album.query.first():
        a1 = Album(name="Discovery", artist="Daft Punk", spotify_id="abc123")
        a2 = Album(name="Abbey Road", artist="The Beatles", spotify_id="def456")
        db.session.add_all([a1, a2])
        print("Seeded albums!")

    # Seed Test User
    if not User.query.filter_by(email="test@test.com").first():
        user = User(
            email="test@test.com",
            username="testuser"
        )
        user.set_password("password123")
        db.session.add(user)
        print("Seeded test user!")

    db.session.commit()