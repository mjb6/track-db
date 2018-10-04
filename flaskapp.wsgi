#!/usr/bin/python3

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import app as application
from app import db
from models import Track, Statistic, Tag
import views

db.connect()
db.create_tables([Track, Statistic, Tag])
db.close()
