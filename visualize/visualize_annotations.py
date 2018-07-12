"""
Display the annotations on top of the images

Usage: python visualize_annotations.py <glob_for_annotation_json_files>

e.g. "../may18to22-first-iteration-annotations/*.json"
"""
import json
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from matplotlib.collections import PatchCollection
import glob
import sys

import os.path
import datetime

from skimage import io


import requests

import pycocotools.mask
import pycocotools.coco
import pycocotools.cocoeval


def jsonprint(obj):
    """Pretty-print JSON"""
    print(json.dumps(obj, indent=4))


print(os.path.abspath(os.path.curdir))
glob_for_annotation_json_files = sys.argv[1]
filenames = glob.glob(glob_for_annotation_json_files)

image_ids = []
for filename in filenames:
    print(filename)
    # mtime = os.path.getmtime(filename)
    # mtime_str = datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')

    with open(filename) as f:
        ann = json.load(f)

        if ann["isObj"] != "1":
            print("isObj is not 1")
            continue
        ans = json.loads(ann["ans"])
        jsonprint(ans)

        results = json.loads(ans["results"])
        assert len(results) == 1  # should be 1 image per task
        image_id, annotations = results.popitem()
        image_ids.append(image_id)

        action_log = json.loads(ans["action_log"])
        jsonprint(results)
        # TODO action log created for each image???

        assert action_log[0]["name"] == "init"
        assert action_log[0]["photo_id"] == image_id
        jsonprint(action_log[0])
        photo_url = action_log[0]["photo_url"]

        time_str = action_log[0]["time"]
        print(photo_url)

        # Retrieve the image that was annotated
        # TODO if on cluster, look directly to stored images rather than making requests
        image = io.imread(photo_url)
        fig = plt.figure()
        title = "%s @ %s" % (image_id, time_str)
        # title = "%s_%s" % (image_id, os.path.basename(filename))
        # TODO make option to only display JPG
        #plt.title(title)
        ax = plt.axes()
        #
        # fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
        #ax.axis('tight')
        ax.axis('off')
        print(image.shape)
        ax.imshow(image, aspect="equal")

        patches = []

        for poly in annotations:
            print(poly)

            # from coco_instance_segmentation.html comment:
            # polygon: [x1,y1,x2,y2,...,xn,yn] x, y are fractions of image width and height
            # TODO height ,width in action log is messed up (the big wide stretched area on v1 of the task?)
            # using the image dimensions seems fine
            # height = action_log[0]["height"]
            # width = action_log[0]["width"]
            height, width = image.shape[0], image.shape[1]

            # Create real x,y points for the image
            xy_coords = [(x*width, y*height) for x, y in zip(poly[::2], poly[1::2])]
            print(xy_coords)
            for x,y in xy_coords:
                plt.scatter(x,y)
            poly_patch = Polygon(xy_coords, edgecolor="red", fill=False, linewidth=3)

            patches.append(poly_patch)

        p = PatchCollection(patches, match_original=True, alpha=0.3)
        ax.add_collection(p)

        # Save annotated images as pngs
        filepath = title + ".png"
        if True: # TODO restore not os.path.exists(filepath):
            extent = ax.get_window_extent().transformed(fig.dpi_scale_trans.inverted())
            plt.savefig(filepath, bbox_inches=extent)  #"tight"
            print("Saved to ", filepath)

# Display with matplotlib
#plt.show()

print("Image IDs used:", image_ids)
