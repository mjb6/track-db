# helpers.py
# helper functions for web views

from datetime import timedelta, datetime

"""Calculate overall statistics of all selected tracks
"""
def calc_statistics(tracks):
    try:
        # Initial values
        distance_m = 0
        duration_s = 0
        elevation_up = 0
        elevation_down = 0
        max_speed = 0
        summed_speed = 0

        for track in tracks:
            distance_m += track.statistics[0].distance_m or 0
            duration_s += track.statistics[0].duration_s or 0
            elevation_up += track.statistics[0].elevation_up_m or 0
            elevation_down += track.statistics[0].elevation_down_m or 0
            summed_speed += track.statistics[0].avg_speed or 0
            if track.statistics[0].max_speed and track.statistics[0].max_speed > max_speed:
                max_speed = track.statistics[0].max_speed

        # construct dict
        overall_statistics = {
            "distance_m": distance_m,
            "duration": duration_s,
            "max_speed": max_speed,
            "avg_speed": summed_speed / float(len(tracks)),
            "elevation_up_m": elevation_up,
            "elevation_down_m": elevation_down
        }
    except Exception as e:
        print(e)  # TODO: use logger, print stacktrace
        overall_statistics = {
            "distance_m": 0,
            "duration": 0,
            "max_speed": 0,
            "avg_speed": 0,
            "elevation_up_m": 0,
            "elevation_down_m": 0
        }

    return overall_statistics


def _convert_time(seconds):
    sec = timedelta(seconds=int(seconds))
    d = datetime(1,1,1) + sec
    return (d.day-1, d.hour, d.minute, d.second)
 

def sec_to_datestring(seconds):
    day, hour, minute, second = _convert_time(seconds)
    return "%d days, %d hours, %d minutes, %d seconds" % (day, hour, minute, second)


def mtr_to_distance(meters):
    km = meters / 1000
    if km >= 1:
        m = meters % 1000
        return "%d,%d km" % (km, m)
    else:
        return "%d meters" % meters
