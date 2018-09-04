"""
Overlay the segmentation annotations on top of the images.

Usage: python visualize_annotations.py <glob_pattern_for_annotation_json_files>

e.g. "../may18to22-first-iteration-annotations/*.json"
"""
import json
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from matplotlib.collections import PatchCollection
import glob
import sys

import os.path

from skimage import io


def jsonprint(obj):
    """Pretty-print JSON"""
    print(json.dumps(obj, indent=4))


def create_annotation(ans):
    """Load the given annotation dict, plot the segments on top of the retrieved image,
    save the annotated image as a file

    Annotation dict keys expected:
    'isObj': "1" or "0"
    'ans': dict containing the various COCO form fields "results" "action_log" etc.
    'action_log': string containing the JSON of the actions recorded by COCO UI (including photo ID & URL)

    Returns:
        filepath if successful, empty string otherwise
    """
    jsonprint(ann)
    if ann["isObj"] != "1":
        print("Skipping annotation with isObj=\'%s\'" % ann['isObj'])
        return ''

    # Load the annotation JSON
    ans = json.loads(ans["ans"])
    results = json.loads(ans["results"])
    assert len(results) == 1  # should be 1 image per task
    jsonprint(results)

    image_id, annotations = results.popitem()
    image_ids.append(image_id)

    # Get the action log which contains the photo URL and other information
    action_log = json.loads(ans["action_log"])

    assert action_log[0]["name"] == "init"
    assert action_log[0]["photo_id"] == image_id
    jsonprint(action_log[0])
    photo_url = action_log[0]["photo_url"]

    time_str = action_log[0]["time"]
    print(photo_url)

    # Retrieve the image that was annotated
    # TODO if on cluster, could load stored images rather than making requests to the remote URL
    image = io.imread(photo_url)
    fig = plt.figure()
    title = "%s @ %s" % (image_id, time_str)

    # title = "%s_%s" % (image_id, os.path.basename(filename))
    # TODO make option to only display JPG
    # plt.title(title)
    ax = plt.axes()
    #
    # fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    # ax.axis('tight')
    ax.axis('off')
    print(image.shape)
    ax.imshow(image, aspect="equal")

    patches = []

    colors = ["aqua", "lime", "magenta"]
    # hatches don't seem to work
    # hatches = ['/', '+', 'o', 'x', '*']
    # plt.rcParams.setdefault('hatch.linewidth', 5)

    for i, poly in enumerate(annotations):
        color = colors[i % len(colors)]
        # hatch = hatches[i % len(hatches)]
        print(poly)

        # from coco_instance_segmentation.html comment:
        # polygon: [x1,y1,x2,y2,...,xn,yn] x, y are fractions of image width and height
        # TODO height ,width in action log is messed up (the big wide stretched area on v1 of the task?)
        # using the image dimensions seems fine
        # height = action_log[0]["height"]
        # width = action_log[0]["width"]
        height, width = image.shape[0], image.shape[1]

        # Create real x,y points for the image
        xy_coords = [(x * width, y * height) for x, y in zip(poly[::2], poly[1::2])]
        print(xy_coords)
        for x, y in xy_coords:
            plt.scatter(x, y)
        poly_patch = Polygon(xy_coords, linewidth=4, color=color, fill=True)  # hatch=hatch

        patches.append(poly_patch)

    p = PatchCollection(patches, match_original=True, alpha=0.3)
    ax.add_collection(p)

    # Save annotated images as pngs
    filepath = title + ".png"
    if True:  # TODO restore not os.path.exists(filepath):
        extent = ax.get_window_extent().transformed(fig.dpi_scale_trans.inverted())
        plt.savefig(filepath, bbox_inches=extent)  # "tight"
        print("Saved to ", filepath)

    return filepath


if __name__ == "__main__":
    print("Current directory:", os.path.abspath(os.path.curdir))
    glob_for_annotation_json_files = sys.argv[1]
    filenames = glob.glob(glob_for_annotation_json_files)

    image_ids = []

    for filename in filenames:
        print(filename)
        with open(filename) as f:
            ann = json.load(f)
            ret = create_annotation(ann)
            if ret == '':
                print("No annotation for", filename, "flagged image?")

    # Display with matplotlib
    #plt.show()

    print("Image IDs used:", image_ids)
