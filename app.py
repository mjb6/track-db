# app.py
import os

from flask import Flask
from peewee import SqliteDatabase
# from revproxy import ReverseProxied

APP_ROOT = os.path.dirname(os.path.realpath(__file__))
DATABASE = os.path.join(APP_ROOT, 'tracks.db')
DEBUG = False

app = Flask(__name__)
app.config.from_object(__name__)
# Activate following line, if you want to access the app through a reverse proxy from a different url-path than /
# app.wsgi_app = ReverseProxied(app.wsgi_app, script_name="/trackdb-test")
db = SqliteDatabase(app.config['DATABASE'], pragmas={'foreign_keys': 1})
