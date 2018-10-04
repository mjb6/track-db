# main.py
from app import app, db
from models import Track, Statistic, Tag
import views

if __name__ == '__main__':
    db.connect()
    db.create_tables([Track, Statistic, Tag])
    db.close()
    app.run()
