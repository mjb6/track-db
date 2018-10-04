
import os
from lib.gpx import Gpx

#gpx = Gpx("ok.gpx")
gpx = Gpx("rr.gpx")
#gpx = Gpx("laufen.gpx")
#gpx = Gpx("test/integration/valid.gpx")
data = gpx.process(force=True)

a=gpx.geo_data

print(data)