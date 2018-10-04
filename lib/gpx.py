"""helper library to read and process data from gpx files
"""

import os
import logging
import time
import datetime
from math import radians, atan2, sin, cos, sqrt
from lxml import etree

# The schema file is based on the original gpx.xsd from topografix.com
# Differences:
# - MinOccurs of trk: 1 instead of 0
# - MinOccurs of trkseg: 1 instead of 0
# - MinOccurs of wpt: 3 instead of 0
GPX_SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "gpx_lib.xsd")

# Namespace of schema
SCHEMAMAP = {'gpx': 'http://www.topografix.com/GPX/1/1'}


class Gpx(object):
    """Read, validate and parse GPX File.
    Store and provide trackpoint information in class attributes.

    @param gpx_file: file to the gpx track
    @skip_inactive: only consider trackpoints with active movement
    """

    def __init__(self, gpx_file, skip_inactive=True):
        self.skip_inactive=skip_inactive
        self.gpx_etree = None
        self.gpx_trackpoints = []
        self.geo_data = {
            "absolute_timestamps" : [],
            "relative_timestamps" : [],
            "differential_timestamps" : [],
            "elevations" : [],
            "lons" : [],
            "lats" : [],
            "active": [],  # boolean predicate if active or paused
            "differential_distances" : [0],
            "differential_ascent" : [0],
            "differential_descent" : [0],
            "differential_speed" : [0],
            }

        self.gpx_file = gpx_file


    def _is_valid(self):
        """validate the gpx_etree object containing the gpx data against the gpx xsd schema
        log a warning if file is invalid

        @return: False if validation error, True if valid gpx
        """
        xmlschema = etree.XMLSchema(file=GPX_SCHEMA_FILE) # pylint: disable=no-member

        if not xmlschema.validate(self.gpx_etree):
            for error in xmlschema.error_log:
                logging.getLogger("validation").warning("Invalid element in GPX File in Line " +
                                                        str(error.line) + ": " + str(error.message))
            return False
        else:
            logging.getLogger("validation").debug("GPX file validation: OK.")
            return True


    def _parse(self, force=False):
        """validate and parse the gpx file, store ElementTree objects of waypoints in attribute list

        @param force: boolean decision whether to continue processing the file on validation error
        """
        if not os.path.isfile(self.gpx_file):
            raise RuntimeError("Can not find file: " + str(self.gpx_file))

        self.gpx_etree = etree.parse(self.gpx_file)  # pylint: disable=no-member

        if not self._is_valid():
            if force:
                logging.getLogger("gpx").warning("--force option is set.\
                I try to continue processing your broken GPX file. \
                Don't blame me if anything unexpected happens.")
            else:
                raise ValueError("Invalid GPX File.")

        root_elem = self.gpx_etree.getroot()

        # find all gpx_trackpoints of all segments of all tracks
        self.gpx_trackpoints.extend(root_elem.findall(".//gpx:trkpt", namespaces=SCHEMAMAP))


    def _extract_geo_data(self):
        """extract latitude, longitude, elevation and timestamp of each waypoint of the gpx.
        store values in geo_data attributes
        """
        self.date = self.gpx_trackpoints[0].find("gpx:time", namespaces=SCHEMAMAP).text
        starttime = convert_date_to_timestamp(self.date)

        for trkpt in self.gpx_trackpoints:
            date = trkpt.find("gpx:time", namespaces=SCHEMAMAP).text
            lon = trkpt.get("lon")
            lat = trkpt.get("lat")
            elevation_element = trkpt.find("gpx:ele", namespaces=SCHEMAMAP)
            if elevation_element is None:  # Skip incomplete trackpoints
                continue

            elevation = elevation_element.text
            timestamp = convert_date_to_timestamp(date)

            if len(self.geo_data["absolute_timestamps"]) == 0:
                self.geo_data["differential_timestamps"].append(0)  # first element
                self.geo_data["active"].append(True)
            else:
                delta = timestamp - self.geo_data["absolute_timestamps"][-1]
                self.geo_data["differential_timestamps"].append(delta)
                if delta < 30:  # consider inactive (e.g. break)  if more than 30 sec between two points
                    self.geo_data["active"].append(True)
                else:
                    self.geo_data["active"].append(False)

            self.geo_data["absolute_timestamps"].append(timestamp)
            self.geo_data["relative_timestamps"].append(timestamp - starttime)
            self.geo_data["elevations"].append(float(elevation))
            self.geo_data["lons"].append(float(lon))
            self.geo_data["lats"].append(float(lat))


    def _calc_diff_geo_data(self):
        """calculate the differential values of geo_data
        """
        for elevation1, lat1, lon1, elevation2, lat2, lon2, active in zip(
                self.geo_data["elevations"][:-1],
                self.geo_data["lats"][:-1],
                self.geo_data["lons"][:-1],
                self.geo_data["elevations"][1:],
                self.geo_data["lats"][1:],
                self.geo_data["lons"][1:],
                self.geo_data["active"][:-1]):

            diff_dist = distance_between(lon1, lon2, lat1, lat2)
            if diff_dist <= 0.75:  # consider inactive (not moving), if diff distance < 0.75m between two points
                active = False

            self.geo_data["differential_distances"].append(distance_between(lon1, lon2, lat1, lat2))
            self.geo_data["differential_ascent"].append(ascent_between(elevation1, elevation2))
            self.geo_data["differential_descent"].append(descent_between(elevation1, elevation2))

        for diff_time, diff_dist in zip(self.geo_data["differential_timestamps"], self.geo_data["differential_distances"]):
            if diff_time == 0:
                continue
            diff_speed = float(diff_dist) / float(diff_time)

            if diff_speed > 30:  # Set diff speed to zero, if calc speed is greater than 110km/h (30m/s)
                diff_speed = 0
                print("Ignoring calculated speed greater than 110km/h")
            self.geo_data["differential_speed"].append(diff_speed)


    def process(self, force=False):
        """validate and parse the gpx file, extract and store waypoint information in lists

        @param force: boolean decision whether to continue processing the file on validation error
        """
        self._parse(force)
        self._extract_geo_data()
        self._calc_diff_geo_data()
        return self.metadata()


    def gpx_update_elevation(self):
        """write values from self.elevations into xml tree

        useful if you change the values in self.elevation, e.g. by applying a filter
        """
        for elevation, tree_elem in zip(self.geo_data["elevations"], self.gpx_trackpoints):
            tree_elem.find("gpx:ele", namespaces=SCHEMAMAP).text = str(elevation)

        return self.gpx_etree


    def metadata(self):
        """return all metadata as dictionary
        """
        return {
            "total_distance": total_distance(self.geo_data, self.skip_inactive),
            "duration": total_duration(self.geo_data, self.skip_inactive),
            "total_duration": total_duration(self.geo_data, False),
            "total_ascent": total_ascent(self.geo_data),
            "total_descent": total_descent(self.geo_data),
            "avg_speed": avg_speed(self.geo_data, self.skip_inactive),
            "max_speed": max_speed(self.geo_data),
            "date": self.date,
        }



# Helper functions at trackpoint level

def distance_between(lon1, lon2, lat1, lat2):
    """calculates the distance between two lon/lat combinations

    using haversine formula: https://en.wikipedia.org/wiki/Haversine_formula

    @return: distance in meters (float)
    """
    earth_radius = 6379000 # Radius of earth in meters

    lon1 = radians(lon1)
    lon2 = radians(lon2)
    lat1 = radians(lat1)
    lat2 = radians(lat2)

    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = (sin(dlat/2))**2 + cos(lat1) * cos(lat2) * (sin(dlon/2))**2 # pylint: disable=invalid-name
    c = 2 * atan2(sqrt(a), sqrt(1-a))  # pylint: disable=invalid-name
    d = earth_radius * c  # pylint: disable=invalid-name
    return d


def ascent_between(elevation1, elevation2):
    """calculates the climb (ascent) between two elevations

    @return: climb in meters (float)
    """
    if elevation2 > elevation1:
        ascent = elevation2 - elevation1
        return ascent
    else:
        return 0.0


def descent_between(elevation1, elevation2):
    """calculates the descent between two elevations

    @return: descent in meters (float)
    """
    if elevation1 > elevation2:
        decent = elevation1 - elevation2
        return decent
    else:
        return 0.0


# Helper functions on whole geo_data level:
def total_duration(geo_data, skip_inactive):
    """return the total duration in sec
    @param: geo_data: dict with geografic data
    @param: skip_inactive: consider only trackpoints with movement (active)
    """
    rel_time = geo_data["relative_timestamps"][-1]

    if skip_inactive:
        inactive_time = 0
        for diff_time, active in zip(geo_data["differential_timestamps"], geo_data["active"]):
            if active == False:
                inactive_time += diff_time

        rel_time = rel_time - inactive_time
    return rel_time


def total_distance(geo_data, skip_inactive):
    """return the total distance in meters
    @param: geo_data: dict with geografic data
    @param: skip_inactive: consider only trackpoints with movement (active)
    """
    sum_distance = 0.0
    for distance, active in zip(geo_data["differential_distances"], geo_data["active"]):
        if skip_inactive and active == False:
            continue
        sum_distance += distance

    return sum_distance


def avg_speed(geo_data, skip_inactive):
    """return the average speed in km/h as float
    """
    speed = 3.6 * total_distance(geo_data, skip_inactive) / float(total_duration(geo_data, skip_inactive))
    return speed



def max_speed(geo_data):
    """return the max. speed  in km/h as float
    """
    max_speed = max(geo_data["differential_speed"])
    max_speed = round(max_speed * 3.6, 1)  # differential_speed is in m/s, we need km/h
    return max_speed



# TODO: unify distance_in_time and total_distance
def distance_in_time(geo_data, start_time=0, end_time=float("inf")):
    """return the distance between start_time and end_time
    """
    sum_distance = 0

    for number, distance in enumerate(geo_data["differential_distances"]):
        if geo_data["relative_timestamps"][number] > end_time:
            break
        if geo_data["relative_timestamps"][number] >= start_time:
            sum_distance += distance

    return sum_distance


def total_ascent(geo_data):
    """return the total ascent in meters
    """
    sum_ascent = 0.0
    for ascent in geo_data["differential_ascent"]:
        sum_ascent += ascent

    return sum_ascent


def total_descent(geo_data):
    """return the total descent in meters
    """
    sum_descent = 0.0
    for ascent in geo_data["differential_descent"]:
        sum_descent += ascent

    return sum_descent


# Generic helper functions:
def convert_date_to_timestamp(date):
    """take a date (as defined in gpx standard), return the corresponding timestamp

    @return: timestamp
    """
    date_format = "%Y-%m-%dT%H:%M:%SZ"

    return int(time.mktime(datetime.datetime.strptime(date, date_format).timetuple()))
