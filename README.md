# gdal_ovr_merge
Modified version of gdal_merge.py script to support merging of ovr files also.

Standard gdal_merge.py script cannot deal with external overview files (.ovr), since these files do not themselves contain georeferencing data. The georeferencing data is saved in the actual image file. To resolve this problem, when merging ovr files, some metadata will be loaded from the actual imagefile, and used in the merging process.
