#! /usr/bin/python3
###############################################################################
#
# Purpose:  Script to merge external overview files (.tif.ovr) for GTiff images.
# Author:   Jeremias Penttilä, jp4896@protonmail.com
#
###############################################################################


import math
import os.path
import sys
import time
import numpy as np

from osgeo import gdal

from PIL import Image
from PIL import ImageSequence

Image.MAX_IMAGE_PIXELS = None


def get_ovr_pages(filename):
    fh = Image.open(filename)
    if fh is None:
        sys.exit(1)

    # Open different pages from the ovr file. Have to use copy... takes about two seconds per image
    pages = []
    for i, page in enumerate(ImageSequence.Iterator(fh)):
        pages.append(page.copy())
    return pages


def get_tif_file(filename):
    filename_aux = filename.rstrip('.ovr')
    fh_aux = gdal.Open(filename_aux)
    if fh_aux is None:
        print("Error, could not find tif file for overlay file: " + filename)
        sys.exit(1)
    return fh_aux


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

    # Calculate some metadata from the first image in the mosaic, all images should be same
    print("Calculating metadata on first image")
    ovr_pages_0 = get_ovr_pages(names[0])
    tif_file_0 = get_tif_file(names[0])
    geotransform_0 = tif_file_0.GetGeoTransform()
    level_widths = [x.size for x in ovr_pages_0]
    tile_w = tif_file_0.RasterXSize
    tile_h = tif_file_0.RasterYSize

    # dont support rotated images at this time
    assert(geotransform_0[2] == 0)
    assert(geotransform_0[4] == 0)

    # Calculate rest of metadata from all the images of the mosaic, requries one iteration over all data.
    # Also run asserts to make sure the files have same required properties
    min_x = min_y = float('inf')
    max_x = max_y = float('-inf')
    print("Calculating metadata across the mosaic")
    for filename in names:
        assert(filename.endswith(".ovr"), "Filename does not end with .ovr this script only support merging of ovr files")
        tif_file = get_tif_file(filename)
        tif_geotransform = tif_file.GetGeoTransform()

        # Make sure that all pyramid levels are same across the mosaic. Dont use get_ovr_pages since it's runtime is long
        assert ([x.size for x in ImageSequence.Iterator(
            Image.open(filename))] == level_widths)

        # Make sure that tif image is same size across the mosaic
        assert(tif_file.RasterXSize == tile_w)
        assert(tif_file.RasterYSize == tile_h)

        # Make sure that image affine transformations are same accross the mosaic
        assert(tif_geotransform[1] == geotransform_0[1])
        assert(tif_geotransform[2] == geotransform_0[2])
        assert(tif_geotransform[4] == geotransform_0[4])
        assert(tif_geotransform[5] == geotransform_0[5])

        # Update x/y min/max values if required
        if tif_geotransform[0] > max_x:
            max_x = tif_geotransform[0]
        elif tif_geotransform[0] < min_x:
            min_x = tif_geotransform[0]
        if tif_geotransform[3] > max_y:
            max_y = tif_geotransform[3]
        elif tif_geotransform[3] < min_y:
            min_y = tif_geotransform[3]

    # Calculate the corners of the image
    min_y = min_y + (tile_h * geotransform_0[5])
    max_x = max_x + (tile_w * geotransform_0[1])

    # Calculate how many x-y tiles the merged image consists of
    num_x_tiles = abs(int((max_x-min_x) / (tile_w * geotransform_0[1])))
    num_y_tiles = abs(int((max_y-min_y) / (tile_h * geotransform_0[5])))

    im_merged_w = num_x_tiles * tile_w
    im_merged_h = num_y_tiles * tile_h
    print(f"Size of merged tiff image is: {(im_merged_w, im_merged_h)}")
    for i in range(0, len(ovr_pages_0)):
        ovr_page_size = ovr_pages_0[i].size
        print(
            f"Merging level: {i}, tile size: {ovr_page_size}, image size: {(ovr_page_size[0] * num_x_tiles, ovr_page_size[1] * num_y_tiles)}")
        dst_ds = gdal.GetDriverByName('GTiff').Create('pil_temp.tif', xsize=(ovr_page_size[0] * num_x_tiles), ysize=(ovr_page_size[1] * num_y_tiles),
                                                      bands=len(ovr_pages_0[0].getbands()), eType=gdal.GDT_Byte, options=["COMPRESS=JPEG", "TILED=YES", "NUM_THREADS=ALL_CPUS","BIGTIFF=YES"])
        pr = 0
        print("Progress: 0", end="")
        for filename in names:
            tile_pages = get_ovr_pages(filename)
            tile = get_tif_file(filename)
            # First need to calculate the location of the tif tile in the merged image
            geotransform = tile.GetGeoTransform()
            xw = geotransform[0]  # World x-coord of the top left pixel
            yw = geotransform[3]  # World y-coord of the top left pixel
            x_im = int((xw - min_x) / geotransform[1])
            y_im = int((yw - max_y) / geotransform[5])

            # based on the location of the tif tile , need to calculate the location of the ovr tile in the smaller merged ovr image
            tile_ovr_page = tile_pages[i]
            x_scaling_factor = tile_ovr_page.size[0] / tile.RasterXSize
            y_scaling_factor = tile_ovr_page.size[1] / tile.RasterYSize
            x_ovr = math.floor(x_scaling_factor * x_im)
            y_ovr = math.floor(y_scaling_factor * y_im)

            for band, b_i in zip(tile_ovr_page.getbands(), range(1, dst_ds.RasterCount+1)):
                band_data = np.array(tile_ovr_page.getchannel(band))
                dst_ds.GetRasterBand(b_i).WriteArray(
                    band_data, int(x_ovr), int(y_ovr))
            dst_ds.FlushCache()
            pr += 1
            progress = math.floor((pr/len(names))*100 / 10) * 10
            print(f"..{progress}" , end=("\n" if progress == 100 else ""))
        os.rename('pil_temp.tif', out_file + (i * ".ovr"))
    return 0


if __name__ == '__main__':
    sys.exit(main())
