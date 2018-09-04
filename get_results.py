"""
Download the MTurk assignments for a given set of tasks,
and save the segmentation annotations overlaid on their respective images.

Warning: this script assumes 1 label per HIT!

Usage: python get_results.py <optional_previous_assignments.pickle>
"""
import json
import os
import sys

import pickle
import datetime

import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from matplotlib.collections import PatchCollection

from skimage import io

import boto3
import xmltodict

# add your aws keys to keys.json
aws_key = json.load(open("keys.json"))
config = json.load(open("configs/config_instance_segmentation.json"))
HIT = config["HIT"]

if HIT["USE_SANDBOX"]:
    endpoint_url = "https://mturk-requester-sandbox.us-east-1.amazonaws.com"
else:
    endpoint_url = "https://mturk-requester.us-east-1.amazonaws.com"

# create mturk connection through boto3
mturk = boto3.client('mturk',
                     aws_access_key_id = aws_key["aws_access_key_id"],
                     aws_secret_access_key = aws_key["aws_secret_access_key"],
                     region_name=HIT["REGION_NAME"],
                     endpoint_url=endpoint_url
                     )


def get_mturk_hits_for_this_group_id(group_id):
    """Get results for all HITs from requester. Returns dict mapping each hit_id to its responses"""
    paginator = mturk.get_paginator('list_hits')
    response_iterator = paginator.paginate()  # why API so bad amazon?
    hit_ids = []
    for resp in response_iterator:
        print(resp)
        for hit in resp["HITs"]:
            if hit["HITGroupId"] == group_id:
                print("found match:", hit)
                hit_ids.append(hit["HITId"])
            # hit_ids.append(hit["HITId"])

    print(len(hit_ids), "hits for groupid=", group_id)
    return hit_ids


def get_reviewable_mturk_hits(type_id=None):
    """Get results for all HITs from requester. Returns dict mapping each hit_id to its responses"""
    paginator = mturk.get_paginator('list_reviewable_hits')
    if type_id is not None:
        response_iterator = paginator.paginate(HITTypeId=type_id, MaxResults=100)
    else:
        response_iterator = paginator.paginate(MaxResults=100)

    hit_ids = []
    for resp in response_iterator:
        for hit in resp["HITs"]:
            hit_ids.append(hit["HITId"])
    print(len(hit_ids), "hits for typeid=", type_id)
    return hit_ids


def main():
    print("Warning: THIS SCRIPT WILL BREAK IF using > 1 assignment per HIT!")

    # Find all the HITs (all that is needed is a list of HIT ids, so they can come from the MTurk API or a file)

    # type_id = "359956SLTYYELSVJCP4WHHMO02URLX"
    # type_id = "37UC2S9IBM29MNF6FUS8ETWH8PY5M2"
    type_id = "3QO1BWENXSM9LUEPUJI2MVSQNTH5ZK"  # v0.4
    # group_id = "3TJWA4I73GA1690MS2C6MWYR2W312X" # v0.2 real mturk test
    # group_id = "3ZSDUF3VWNHXGCE1F6QPAPDO0HE23P" # v0.3 real mturk test
    # hit_ids = get_mturk_hits_for_this_group_id(group_id)
    #
    # with open("hits/2018_07_28_09:30:49_hits.json") as f:
    #     hits = json.load(f)
    #     hit_ids = list(hits.keys())
    # with open("hits_11800.txt") as f:
    #     hit_ids = [line.strip() for line in f]
    hit_ids = get_reviewable_mturk_hits(type_id=type_id)

    # If provided, start with the last set of assignments downloaded
    if len(sys.argv) > 1:
        previous_assignments_filename = sys.argv[1]
        assignments = pickle.load(open(previous_assignments_filename, 'rb'))
        flagged_assignments = pickle.load(open("flagged_" + previous_assignments_filename, 'rb'))
    else:
        assignments = []
        flagged_assignments = []

    print(len(assignments), "assignments previously downloaded")
    hits_completed_already = set(a['HIT']['HITId'] for a in assignments)
    hit_ids = [hit for hit in hit_ids if hit not in hits_completed_already]

    print(len(hit_ids), "hits that have not been downloaded already")

    # Save annotated images as PNGs or log bad images/ other errors
    out_dir = "result_images"
    if not os.path.exists(out_dir):
        os.mkdir(out_dir)

    num_already_saved = len(assignments)

    for hit_id in hit_ids:
        worker_results = mturk.list_assignments_for_hit(HITId=hit_id)

        for assignment in worker_results['Assignments']:
            worker_id = assignment['WorkerId']
            assignment_id = assignment['AssignmentId']

            filepath = os.path.join(out_dir, type_id, "worker%s_assignment%s.png" % (worker_id, assignment_id))
            if os.path.exists(filepath):
                # Skip if annotation already created
                num_already_saved += 1
                continue

            response = mturk.get_assignment(
                AssignmentId=assignment['AssignmentId']
            )
            assignments.append(response)

            print("worker_id", worker_id)
            print("assignment_id", assignment_id)

            xml_doc = xmltodict.parse(response['Assignment']['Answer'])
            isObj, ans = None, None
            for ans in xml_doc['QuestionFormAnswers']['Answer']:
                if ans['QuestionIdentifier'] == 'isObj':
                    isObj = int(ans['FreeText'])
                if ans['QuestionIdentifier'] == "ans":
                    ans = json.loads(ans['FreeText'])

            if isObj == 0:
                # Flagged as not containing the object, skip here
                print("isObj=0, skipping")
                # Added to this list when turker flags image as not containing object
                flagged_assignments.append(response)
                continue

            # Display the annotations on top of the images
            results = json.loads(ans["results"])
            assert len(results) == 1  # should be 1 image per task
            image_id, annotations = results.popitem()

            action_log = json.loads(ans["action_log"])
            # TODO action log created for each image???

            assert action_log[0]["name"] == "init"
            assert action_log[0]["photo_id"] == image_id
            photo_url = action_log[0]["photo_url"]

            # Retrieve the image that was annotated
            # TODO if on cluster, could look directly to stored images rather than making requests
            image = io.imread(photo_url)
            fig = plt.figure()
            ax = plt.axes()
            ax.axis('off')
            ax.imshow(image, aspect="equal")

            patches = []

            for poly in annotations:
                # from coco_instance_segmentation.html comment:
                # polygon: [x1,y1,x2,y2,...,xn,yn] x, y are fractions of image width and height
                height, width = image.shape[0], image.shape[1]

                # Create real x,y points for the image
                xy_coords = [(x * width, y * height) for x, y in zip(poly[::2], poly[1::2])]
                for x, y in xy_coords:
                    plt.scatter(x, y)
                poly_patch = Polygon(xy_coords, edgecolor="red", fill=False, linewidth=3)

                patches.append(poly_patch)

            p = PatchCollection(patches, match_original=True, alpha=0.3)
            ax.add_collection(p)

            if not os.path.exists(filepath):
                extent = ax.get_window_extent().transformed(fig.dpi_scale_trans.inverted())
                plt.savefig(filepath, bbox_inches=extent)  # "tight"
                print("Saved to ", filepath)

    print("Number of assignments completed", len(assignments), "with", num_already_saved, "already saved")

    # Save all assignments in a pickle file in the data/ folder
    timestamp = datetime.datetime.utcnow().strftime("%Y_%m_%d_%H:%M:%S")
    assignments_pickle = "data/assignment_pickles/assignments_%s.pickle" % timestamp
    with open(assignments_pickle, 'wb') as pf:
        pickle.dump(assignments, pf)
        print("Saved to", assignments_pickle)

    print("# of flagged assignments:", len(flagged_assignments))
    flagged_pickle = "data/assignment_pickles/flagged_assignments_%s.pickle" % timestamp
    with open(flagged_pickle, 'wb') as pf:
        pickle.dump(flagged_assignments, pf)
        print("Saved to", flagged_pickle)

    # Save a second copy with a fixed name for convenient reloading on server
    latest_assignments_pickle = "data/assignment_pickles/assignments_latest.pickle"
    with open(latest_assignments_pickle, 'wb') as pf:
        pickle.dump(assignments, pf)
        print("Saved to", latest_assignments_pickle)

    print("# of flagged assignments:", len(flagged_assignments))
    latest_flagged_pickle = "data/assignment_pickles/flagged_assignments_latest.pickle"
    with open(latest_flagged_pickle, 'wb') as pf:
        pickle.dump(flagged_assignments, pf)
        print("Saved to", latest_flagged_pickle)



if __name__ == "__main__":
    main()
