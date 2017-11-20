"""
Creates an OBJ mesh from a DEM
If using blender, I suggest opening with the following settings
    z up
    +y forward

Copyright 2017 Steven Kay

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this list of
conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
this list of conditions and the following disclaimer in the documentation and/or
other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY
EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES
OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

import logging
import argparse
import random

import rasterio


class RasterReader:

    def __init__(self):
        self.size = None

    def get_metadata(self, filename):
        metadata = {}
        with rasterio.open(filename, 'r') as src:
            matrix = src.affine
            tl_x, tl_y = matrix * (0, 0)
            br_x, br_y = matrix * (src.width - 1, src.height - 1)
            metadata["center_x"] = (tl_x + br_x) / 2.0
            metadata["center_y"] = (tl_y + br_y) / 2.0
            metadata["width"] = src.width
            metadata["height"] = src.height
            metadata["size_x"] = (tl_x - br_x) / src.width
            metadata["size_y"] = (tl_y - br_y) / src.width
        return metadata

    def load_raster_xyz(self, filename):
        """
        Spit out x,y,z tuples.
        :param filename: file name to load
        :return: series of (x,y,z)
        """
        with rasterio.open(filename, 'r') as src:
            matrix = src.affine
            self.size = (src.width, src.height)
            # read per scan line
            for row in range(0, src.height):
                window = ((row, row+1), (0, src.width))
                data = src.read(window=window)
                this_row = data[0][0]
                for column in range(0, src.width):
                    x, y = matrix * (column, row)
                    yield x, y, this_row[column]


class ObjBuilder:

    def __init__(self, size):
        """
        :param size: tuple (width, height)
        """
        self.size = size
        self.vertices = []

    def add_vertex(self, vertex):
        """
        add vertex
        :param vertex: (x,y,z) values as tuple
        :return:
        """
        self.vertices.append(vertex)

    def vertex_num(self, x, y):
        """
        Computes vertex number from x and y
        :param x:
        :param y:
        :return:
        """
        width, _ = self.size
        return 1 + (width*y) + x

    def write_file(self, filename):
        """
        Writes OBJ format
        each pixel converted to 2 tris
        :param filename:
        :return:
        """
        with open(filename, "w") as fo:
            # vertices

            for x, y, z in self.vertices:
                fo.write("v {} {} {}\n".format(x, y, z))
            logging.info("Wrote {} vertices".format(len(self.vertices)))

            # faces
            faces = 0
            width, height = self.size
            for y in range(0, height-1):
                for x in range(0, width-1):
                    tl = self.vertex_num(x,y)
                    tr = tl + 1
                    bl = tl + width
                    br = bl + 1
                    fo.write("f {} {} {}\n".format(tl, tr, bl))
                    fo.write("f {} {} {}\n".format(tr, br, bl))
                    faces += 2
            logging.info("Wrote {} tris".format(faces))


def main():

    parser = argparse.ArgumentParser(description='Convert DEM to OBJ format tri mesh')
    parser.add_argument("-i", "--input", nargs=1, help="filename of a GDAL-supported raster format DEM", required=True)
    parser.add_argument("-o", "--output", nargs=1, help="filename to write to", required=True)
    parser.add_argument("-x", "--exaggeration", type=float, nargs=1, help="vertical exaggeration (default 1.0)", required=False)
    parser.add_argument("-s", "--scaling", type=float, nargs=1, help="global scaling (default 0.001)", required=False)
    parser.add_argument("-v", "--verbose", action='store_true', help="verbose (show progress & scary messages)", required=False)
    parser.add_argument("-w", "--wgs84", action='store_true',  help="wgs84 settings (x,y in degrees, elevation in meters", required=False)
    parser.add_argument("-j", "--jitter", action='store_true', help="add jitter (small random offset to x and y)", required=False)

    scale = 1.0
    exaggeration = 1.0
    jitter = False

    arguments = parser.parse_args()
    filename = arguments.input[0]
    filename_out = arguments.output[0]
    if arguments.jitter:
        jitter = True
    if arguments.scaling:
        scale = arguments.scaling[0]
    if arguments.exaggeration:
        exaggeration = arguments.exaggeration[0]
    verbose = arguments.verbose
    wgs84 = arguments.wgs84

    if verbose:
        logging.basicConfig(format='%(asctime)s %(message)s', level=logging.DEBUG, datefmt='%m/%d/%Y %I:%M:%S %p')
    else:
        logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO, datefmt='%m/%d/%Y %I:%M:%S %p')

    if wgs84:
        scale = 1.0
        exaggeration = scale/110000.0
        logging.info("Using WGS84 mode (scale={:.2f}, axeggeration={:.8f}".format(scale, exaggeration))

    reader = RasterReader()
    metadata = reader.get_metadata(filename)
    size = (metadata["width"], metadata["height"])
    logging.info("Image size is {}".format(size))
    obj_maker = ObjBuilder(size)
    mid_x, mid_y = (metadata["center_x"], metadata["center_y"])
    logging.info("Mid point at {},{}".format(mid_x, mid_y))

    logging.info("Scanning raster for xyz values...")
    points = 0

    dx = 0.25 * metadata["size_x"]
    dy = 0.25 * metadata["size_y"]

    for x, y, z in reader.load_raster_xyz(filename):
        if not jitter:
            obj_maker.add_vertex(((x-mid_x)*scale, (y-mid_y)*scale, z*scale*exaggeration))
        else:
            x_offset = random.uniform(-dx, dx)
            y_offset = random.uniform(-dy, dy)
            obj_maker.add_vertex(((x - mid_x + x_offset) * scale, (y - mid_y + y_offset) * scale, z * scale * exaggeration))
        points += 1
        if points % 10000 == 0:
            percent = (points/(size[0]*size[1]))*100.0
            logging.debug("Added {} vertices ({:.2f}%)".format(points, percent))
    logging.info("Writing OBJ file...")
    obj_maker.write_file(filename_out)
    logging.info("OBJ file written")


if __name__ == "__main__":
    main()
