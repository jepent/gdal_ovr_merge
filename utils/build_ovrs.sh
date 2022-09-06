#!/bin/bash

pushd test_images

for f in image_*.tif
do
    gdaladdo $f -ro 2 4 8 16 32
done

popd