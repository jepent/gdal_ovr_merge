#! /usr/bin/python3
###############################################################################
#
# Purpose:  Modified version of OSGeo gdal_merge.py script to support merging of ovr files
# Author:   Jeremias Penttilä, jp4896@protonmail.com
#
###############################################################################


import math
import os.path
import sys
import time

from osgeo import gdal

from PIL import Image
from PIL import ImageSequence
from PIL import TiffImagePlugin


def get_data(names):
    ovr_pages = []
    tif_files = []
    for filename in names:
        fh = Image.open(filename)
        if fh is None:
            sys.exit(1)

        filename_aux = filename.rstrip('.ovr')
        fh_aux = gdal.Open(filename_aux)
        if fh_aux is None:
            print("Error, could not find tif file for overlay file: " + filename)
            sys.exit(1)

        # Open different pages from the ovr file
        pages = []
        for page in ImageSequence.Iterator(fh):
            pages.append(page.copy())
        ovr_pages.append(pages)
        tif_files.append(fh_aux)
    return (ovr_pages, tif_files)


def main(argv=None):
    names = []
    out_file = 'out.tif.ovr'

    if argv is None:
        argv = sys.argv
    argv = gdal.GeneralCmdLineProcessor(argv)
    if argv is None:
        sys.exit(0)

    # Parse command line arguments.
    i = 1
    while i < len(argv):
        arg = argv[i]

        if arg == '-o':
            i = i + 1
            out_file = argv[i]

        elif arg[:1] == '-':
            print('Unrecognized command option: %s' % arg)
            Usage()
            sys.exit(1)

        else:
            names.append(arg)

        i = i + 1

    if not names:
        print('No input files selected.')
        sys.exit(1)

    Driver = gdal.GetDriverByName("GTiff")
    DriverMD = Driver.GetMetadata()

    ovr_pages, tif_files = (get_data(names))

    tile_w = tif_files[0].RasterXSize
    tile_h = tif_files[0].RasterYSize

    level_widths = [ x.size for x in ovr_pages[0]]

    #Make sure that all leveltiles are same size as the one for the first
    for tile_pages in ovr_pages[1:]:
        t = [ x.size for x in tile_pages]
        assert (t == level_widths)

    # Make sure each tile is the same size as the first one
    for tile in tif_files[1:]:
        assert(tile.RasterXSize == tile_w)
        assert(tile.RasterYSize == tile_h)

    # Calculate the corners of the image
    geotransforms = [tile.GetGeoTransform() for tile in tif_files]
    for x in geotransforms[1:]:
        assert(x[1] == geotransforms[0][1])
        assert(x[2] == geotransforms[0][2])
        assert(x[4] == geotransforms[0][4])
        assert(x[5] == geotransforms[0][5])
    min_x = min([x[0] for x in geotransforms])
    min_y = min([x[3] for x in geotransforms]) + (tile_h * geotransforms[0][5])
    max_x = max([x[0] for x in geotransforms]) + (tile_w * geotransforms[0][1])
    max_y = max([x[3] for x in geotransforms])

    # dont support rotated images at this time
    assert(geotransforms[0][2] == 0)
    assert(geotransforms[0][4] == 0)

    # Calculate how many x-y tiles the merged image consists of
    num_x_tiles = abs(int((max_x-min_x) / (tile_w * geotransforms[0][1])))
    num_y_tiles = abs(int((max_y-min_y) / (tile_h * geotransforms[0][5])))

    im_merged_w = num_x_tiles * tile_w
    im_merged_h = num_y_tiles * tile_h


    image_list = []

    for i in range(0,len(ovr_pages[0])):
        ovr_page_size = ovr_pages[0][i].size
        merged_ovr_tile = Image.new(ovr_pages[0][i].mode,(ovr_page_size[0] * num_x_tiles, ovr_page_size[1] * num_y_tiles)) 
        for tile_pages,tile in zip(ovr_pages,tif_files):
            # First need to calculate the location of the tif tile in the merged image
            geotransform = tile.GetGeoTransform()
            xw = geotransform[0] # World x-coord of the top left pixel
            yw = geotransform[3] # World y-coord of the top left pixel
            x_im = int((xw - min_x) / geotransform[1])
            y_im = int((yw - max_y) / geotransform[5])

            ## based on the location of the tif tile , need to calculate the location of the ovr tile in the smaller merged ovr image
            tile_ovr_page = tile_pages[i]
            x_scaling_factor = tile_ovr_page.size[0] / tile.RasterXSize
            y_scaling_factor = tile_ovr_page.size[1] / tile.RasterYSize
            x_ovr = math.floor(x_scaling_factor * x_im)
            y_ovr = math.floor(y_scaling_factor * y_im)

            merged_ovr_tile.paste(tile_ovr_page, (int(x_ovr), int(y_ovr)))
        image_list.append(merged_ovr_tile)        
    image_list[0].save('.pil_temp.tif', compression=None, save_all=True, append_images=image_list[1:])
    os.rename('.pil_temp.tif', out_file)
    return 0


if __name__ == '__main__':
    sys.exit(main())
