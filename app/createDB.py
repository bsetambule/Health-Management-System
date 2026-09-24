from app import create_app
from app.extensions import db

app = create_app("development")  # or "production"

with app.app_context():
    #db.drop_all() #drop tables
    db.create_all()
    print("Tables created successfully")
