# models.py
from app import db
from peewee import *  # pylint: disable=W0614

class Track(Model):
    name = CharField()
    date = DateField()
    path = CharField()

    class Meta:
        database = db  # This model uses the "tracks.db" database.


class Statistic(Model):
    track = ForeignKeyField(Track, backref="statistics")
    distance_m = IntegerField()
    duration_s = IntegerField()
    duration_total_s = IntegerField()
    max_speed = FloatField()
    avg_speed = FloatField()
    elevation_up_m = IntegerField()
    elevation_down_m = IntegerField()

    class Meta:
        database = db  # This model uses the "tracks.db" database.


class Tag(Model):  # TODO: store tags diffently
    track = ForeignKeyField(Track, backref="tags")
    value = CharField()

    class Meta:
        database = db  # This model uses the "tracks.db" database.
