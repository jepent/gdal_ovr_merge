#!/bin/bash

pushd test_images
gdalbuildvrt image.vrt image_*.tif
popd