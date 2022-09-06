import os, gdal
from gdalconst import *

width = 699
height = 929
tilesize = 500

for i in range(0, width, tilesize):
    for j in range(0, height, tilesize):
        gdaltranString = "gdal_translate -of GTIFF -srcwin "+str(i)+", "+str(j)+", "+str(tilesize)+", " \
            +str(tilesize)+" test_images/orig.tif test_images/image_"+str(i)+"_"+str(j)+".tif"
        os.system(gdaltranString)