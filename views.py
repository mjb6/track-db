# views.py
import os
from datetime import date, datetime
from flask import url_for, request, render_template, redirect, flash
from werkzeug.utils import secure_filename
from models import Track, Statistic, Tag
from app import app
from lib.helpers import calc_statistics, mtr_to_distance, sec_to_datestring
from lib.gpx import Gpx

# User config
UPLOAD_DIR = "upload-data"
app.secret_key = b'\xbf/q|vow\xca>\x13\xc8k\x8a\x8e\x99\x15'  # Secret key is used to encrypt the content of the cookie. If you want to prevent this, change the value to another arbitrary one.

# System constants
UPLOAD_BASE_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), "static")
ALLOWED_EXTENSIONS = set(['gpx'])


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
def index():
    return redirect(url_for("show"))


@app.context_processor
def utility_processor():
    """make helper functions available to templates
    """
    def mtr_to_dst(meters):
        return mtr_to_distance(meters)

    def sec_to_date(seconds):
        return sec_to_datestring(seconds)

    return dict(mtr_to_dst=mtr_to_dst, sec_to_date=sec_to_date)


@app.route("/show/", methods=["GET", "POST"])
def show():
    tags = Tag.select(Tag.value).distinct().order_by(Tag.value.asc())  #pylint: disable=E1111
    
    if request.method == "POST":  # Filter the track list based on selected tags
        # Evaluate selected tags, modify tag object with selection
        sel_tags = request.form.getlist('tag-select')
        for tag in tags:
            for sel_tag in sel_tags:
                if tag.value == sel_tag:
                    tag.selected = True

        # Query database
        all_tracks = Track.select().order_by(Track.date.asc())  # pylint: disable=E1111
        tracks = []
        for track in all_tracks:
            tag_elems_for_track = Tag.select().where(Tag.track==track)  # pylint: disable=E1111
            tags_for_track = []
            for elem in tag_elems_for_track:
                tags_for_track.append(elem.value)

            if set(sel_tags).issubset(tags_for_track):
                tracks.append(track)

        # Pass information about selected map
        if len(tracks) == 0:  # No available tracks - give warning
            track_id = None
        elif request.form.get("track-select") == None or request.form.get("track-select") == "":  # No track selected - return latest map
            track_id = len(tracks) - 1
        else:  # Return selected map
            track_id = int(request.form.get("track-select"))


    else:  # List all tracks
        tracks = Track.select().order_by(Track.date.asc())  #pylint: disable=E1111
        # show latest map
        if len(tracks) == 0:
            track_id = None
        else:
            track_id = len(tracks) - 1

    if track_id:
        tags_for_track =  Tag.select(Tag.value).where(Tag.track == tracks[track_id])  #pylint: disable=E1111
    else:
        tags_for_track = ""
    overall_statistics = calc_statistics(tracks)
    return render_template("show.html", tracks=tracks, tags=tags, tags_for_track=tags_for_track, track_id=track_id, overall_statistics=overall_statistics)


@app.route("/delete/<int:track_id>/")
def delete(track_id):
    track = Track.get(Track.id == track_id)
    track_name = track.name
    track_path = track.path
    gpx_fspath = os.path.join(UPLOAD_BASE_DIR, track_path)
    track.delete_instance(recursive=True)
    os.remove(gpx_fspath)
    flash("Track '%s' deleted sucessfully." % track_name, "info")
    return redirect(url_for("show"))


@app.route("/add/", methods=["GET", "POST"])
def add():
    tags = Tag.select(Tag.value).distinct()  #pylint: disable=E1111

    if request.method == "POST":
        # Validate uploaded file
        if 'gpx-file' not in request.files:
            flash("No file uploaded", "error")
            return redirect(request.url)
        gpx_file = request.files['gpx-file']
        if gpx_file.filename == '':
            flash("No file selected", "error")
            return redirect(request.url)
        if not allowed_file(gpx_file.filename):
            flash("Only .gpx files supported!", "error")
            return redirect(request.url)

        # Store gpx file in filesystem
        gpx_filename = secure_filename(gpx_file.filename)
        gpx_filename = "%s_%s.gpx" % (gpx_filename[:-4], int(datetime.now().timestamp()))  # add timestamp to filename
        gpx_fspath = os.path.join(UPLOAD_BASE_DIR, UPLOAD_DIR, gpx_filename)
        os.makedirs(os.path.dirname(gpx_fspath), exist_ok=True)
        gpx_file.save(gpx_fspath)

        try:
            # Use gpx library to extract meta information from gpx file
            gpx = Gpx(gpx_fspath, True)
            gpx_metadata = gpx.process(force=True)  # TODO: improve gpx lib and set force to False

            # Read form values: tags and name
            track_name = request.form.get("name") or "Unnamend activity on %s"% gpx_metadata["date"]
            tags = request.form.getlist('tag-select')
            new_tags = request.form.get("new-tags").replace(" ","")
            if new_tags != "":
                tags += new_tags.split(",")
            tags.append(gpx_metadata["date"][:4])  # implicit add of the year
            tags = set(tags)  # Remove duplicate tags

            # Create DB ORM objects
            new_track = Track(name=track_name, date=gpx_metadata["date"], path=os.path.join(UPLOAD_DIR, gpx_filename))

            # Read statistics
            new_track_stats = Statistic(
                track=new_track,
                distance_m=gpx_metadata["total_distance"],
                duration_s=gpx_metadata["duration"],
                duration_total_s=gpx_metadata["total_duration"],
                max_speed=gpx_metadata["max_speed"],
                avg_speed=gpx_metadata["avg_speed"],
                elevation_up_m=gpx_metadata["total_ascent"],
                elevation_down_m=gpx_metadata["total_descent"]
            )

        except Exception as e:
            flash("Error during gpx file processing: %s" % e, "error")

            # Clean up
            if 'new_track' in locals():
                new_track.delete_instance()
            if 'new_track_stats' in locals():
                new_track_stats.delete_instance()
            os.remove(os.path.join(os.path.dirname(os.path.realpath(__file__)), UPLOAD_BASE_DIR, UPLOAD_DIR, gpx_filename))
            return redirect(request.url)


        # Store objects in DB
        new_track.save()
        new_track_stats.save()

        for tag in tags:
            my_tag = Tag(track=new_track, value=tag)
            my_tag.save()

        
        flash("Track '%s' added sucessfully." % track_name, "info")
        return redirect(url_for("show"))
    else:
        return render_template("add.html", tags=tags)
