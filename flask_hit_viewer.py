"""
Flask webapp to view the MTurk submissions for a given set of segmentation tasks.

Uses a Pandas dataframe to hold the assignment information

Make sure to set RESULT_IMAGE_DIR below to see the annotated images that have been saved previously
"""
import os
import json
import pickle
from collections import defaultdict

import xmltodict
from flask import Flask, jsonify, send_file
import boto3
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from flask import request
import pandas as pd
# Allow long columns in Pandas HTML (tags for images take lots of characters)
pd.set_option('display.max_colwidth', -1)

import get_results
from get_classnames import get_all_machine_learn_nodes

# TODO set the directory where annotated segmentation images are stored
RESULT_IMAGE_DIR = "/path/to/result_images"


# Add your aws keys to keys.json
aws_key = json.load(open("keys.json"))
config = json.load(open("configs/config_instance_segmentation.json"))
HIT = config["HIT"]
if HIT["USE_SANDBOX"]:
    endpoint_url = "https://mturk-requester-sandbox.us-east-1.amazonaws.com"
else:
    endpoint_url = "https://mturk-requester.us-east-1.amazonaws.com"

# Create mturk connection through boto3
mturk = boto3.client('mturk',
                     aws_access_key_id = aws_key["aws_access_key_id"],
                     aws_secret_access_key = aws_key["aws_secret_access_key"],
                     region_name=HIT["REGION_NAME"],
                     endpoint_url=endpoint_url
                     )

# Create Flask app
app = Flask("Flask segmentation HIT viewer")

# type_id = "37UC2S9IBM29MNF6FUS8ETWH8PY5M2"
group_id = "3ZSDUF3VWNHXGCE1F6QPAPDO0HE23P"
assignments_file = "data/assignment_pickles/assignments_2018_07_31_18:49:05.pickle"  # list of assignment Response dicts
all_assignments = pickle.load(open(assignments_file, 'rb'))

# Create Pandas dataframe (one row for each assignment)
data = []
flagged = 0
# Dataframe fields from Assignment JSON
columns = ['HITId', 'AssignmentId', 'WorkerId', 'SubmitTime', 'AssignmentStatus']

for assignment in all_assignments:
    assignment = assignment['Assignment']
    xml_doc = xmltodict.parse(assignment['Answer'])
    duration_dict = [a for a in xml_doc['QuestionFormAnswers']['Answer'] if a['QuestionIdentifier'] == 'duration'][0]
    duration = float(duration_dict['FreeText'])

    # TODO bad for whatever reason in COCO JS the active time is not collected when the user flags the image!!!
    isObj_dict = [a for a in xml_doc['QuestionFormAnswers']['Answer'] if a['QuestionIdentifier'] == 'isObj'][0]
    isObj = int(isObj_dict['FreeText'])
    if isObj == 0:
        time_active_seconds = duration / 1000
        flagged += 1
    else:
        ans_dict = [a for a in xml_doc['QuestionFormAnswers']['Answer'] if a['QuestionIdentifier'] == 'ans'][0]
        ans = json.loads(ans_dict["FreeText"])
        time_active_ms = float(json.loads(ans["time_active_ms"]).popitem()[1][0])
        time_active_seconds = time_active_ms / 1000

    data.append(tuple([assignment[col] for col in columns] + [duration, time_active_seconds, not isObj]))

# Dataframe fields from the COCO UI logs
columns.extend(["duration", "time_active_seconds", "flagged_isObj_as_0"])
df = pd.DataFrame.from_records(data, columns=columns)

output_column = []
for _, row in df.iterrows():
    worker_id, assignment_id = row['WorkerId'], row['AssignmentId']

    result_image = "worker%s_assignment%s.png" % (worker_id, assignment_id) # glob.glob("./result_images/*assignment%s*" % assignment_id)
    if not os.path.exists(os.path.join(RESULT_IMAGE_DIR, result_image)):
        # flagged or not submitted
        output_column.append("flagged_or_not_submitted")
    else:
        image_url = os.path.join("/result_images", os.path.relpath(result_image, "."))

        image_tag = "<img src=\"%s\" height=\"100\" />" % image_url
        output_column.append(image_tag)

# Dataframe field with the image as an HTML <img> tag if present
df['image'] = output_column


@app.route('/routes', methods=['GET'])
def get_routes():
    """Helpful way to see all routes for this Flask app"""
    endpoints = [rule.rule for rule in app.url_map.iter_rules()
                 if rule.endpoint != 'static']
    return jsonify(dict(api_endpoints=endpoints))


@app.route("/recent")
@app.route("/recent/<num_items>")
def get_recent(num_items=100):
    """Show the most recent labels"""
    result = df.sort_values(by="SubmitTime", ascending=False)[:num_items]
    return result.to_html(escape=False, max_cols=None)


@app.route("/stats")
def get_stats():
    """Return aggregate statistics for all assignments (median time, median active time)"""
    assignments_by_worker = defaultdict(list)
    flagged = 0
    for a in all_assignments:
        xml_doc = xmltodict.parse(a['Assignment']['Answer'])
        duration_dict = [a for a in xml_doc['QuestionFormAnswers']['Answer'] if a['QuestionIdentifier'] == 'duration'][0]
        duration = float(duration_dict['FreeText'])
        a['duration'] = duration

        # TODO note: in COCO JS the active time is not collected when the user flags the image!!!
        # Using duration for now!
        isObj_dict = [a for a in xml_doc['QuestionFormAnswers']['Answer'] if a['QuestionIdentifier'] == 'isObj'][0]
        isObj = int(isObj_dict['FreeText'])
        if isObj == 0:
            a['time_active_seconds'] = duration / 1000
            flagged += 1
        else:
            ans_dict = [a for a in xml_doc['QuestionFormAnswers']['Answer'] if a['QuestionIdentifier'] == 'ans'][0]
            ans = json.loads(ans_dict["FreeText"])
            # results = json.loads(ans["results"])

            print(ans.keys())
            print(type(ans["time_active_ms"]))
            time_active_ms = float(json.loads(ans["time_active_ms"]).popitem()[1][0])
            a['time_active_seconds'] = time_active_ms / 1000

        worker_id = a['Assignment']['WorkerId']
        assignments_by_worker[worker_id].append(a)

    exclude = []
    all_assignments_after_5_jobs = []  # remove the first 5 jobs by each worker
    for worker_id in assignments_by_worker:
        if worker_id in exclude: # TODO
            continue
        assignments_by_worker[worker_id].sort(key=lambda a: a['Assignment']['SubmitTime'])
        after_5_jobs = assignments_by_worker[worker_id][5:]

        all_assignments_after_5_jobs.extend(after_5_jobs)

    # Calculate median time for tasks and median active time working on the tasks
    print(len(all_assignments))
    print(len(all_assignments_after_5_jobs))

    median = np.median([a['duration'] for a in all_assignments])
    print(median)
    median_after_5_jobs = np.median([a['duration'] for a in all_assignments_after_5_jobs])
    print(median_after_5_jobs)
    durations5 = np.array([a['duration'] for a in all_assignments_after_5_jobs])

    active_median = np.median([a['time_active_seconds'] for a in all_assignments])
    print(active_median)
    active_median_after_5_jobs = np.median([a['time_active_seconds'] for a in all_assignments_after_5_jobs])
    print(active_median_after_5_jobs)

    active_durations5 = np.array([a['time_active_seconds'] for a in all_assignments_after_5_jobs])

    sns.distplot(durations5, kde=True, bins=100)
    sns.distplot(active_durations5, kde=True, bins=100)
    plt.show()

    return "<br>".join(str(x) for x in [len(all_assignments), flagged, "median after 5 jobs %s" % median_after_5_jobs,
                                        "active median after 5 jobs %s" % active_median_after_5_jobs])


@app.route('/reload', methods=['GET'])
def request_results_update():
    """Tell the server to check for new assignments on MTurk (calls the get_results.py script)"""
    print("Calling get_results script")
    num_assignments = get_results.main()
    return "Updated results, num_assignments=", num_assignments


@app.route("/classes")
def show_examples_from_each_class():
    """Return some example images (as HTML) from each class
    Args:
        nf: number of Food101 images to show
        nb: number of BingCrawl2017 images to show
    """
    # TODO better way to specify NUMBER OF IMAGES FOR EACH CLASS
    nf = request.args.get("nf", 2)
    nb = request.args.get("nb", 2)

    # map_class_id_to_node = get_classnames_bing_food101()
    # class_ids_to_use = [1009, 1967, 1986, 2237, 2277, 2924, 2930, 2931, 2939, 2941]
    map_class_id_to_node = get_all_machine_learn_nodes()
    output = []

    map_food_101_id_to_image_ids = pickle.load(open("pickles/map_food_101_id_to_image_ids.pickle", 'rb'))
    map_bing_id_to_image_ids = pickle.load(open("pickles/map_bing_id_to_image_ids.pickle", 'rb'))
    image_id_to_url = pickle.load(open("pickles/image_id_to_url.pickle", 'rb'))

    def wrap_img_and_link(url):
        return "<a href=\"%s\" target=\"_blank\"><img src=\"%s\" height=\"100\" /></a>" % (url, url)

    for class_id, node in map_class_id_to_node.items():

        display_name = node['display_name_translations']['en']

        image_tags = []
        if 'food_101' in node:
            NUM_FOOD101_IMAGES = int(nf)
            fid = node['food_101']
            food101_urls = [image_id_to_url[i] for i in
                            np.random.choice(map_food_101_id_to_image_ids[fid], NUM_FOOD101_IMAGES)]
            food101_tags = [wrap_img_and_link(url)
                            for url in food101_urls]
            image_tags.extend(['food101 images:'] + food101_tags)

        if 'bing_crawl_2017' in node:
            NUM_BING_IMAGES = int(nb)
            bid = node['bing_crawl_2017']
            bing_urls = [image_id_to_url[i] for i in
                         np.random.choice(map_bing_id_to_image_ids[bid], NUM_BING_IMAGES)]
            bing_tags = [wrap_img_and_link(url)
                         for url in bing_urls]
            image_tags.extend(['bing2017 images:'] + bing_tags)

        # Get some images from Food101 and Bing2017
        output.append(str([class_id, display_name] + [image_tags]))

    return "<br>".join(output)


@app.route("/")
def main_page():
    """Display the full Pandas dataframe"""
    return df.to_html(escape=False, max_cols=None, columns=['AssignmentId', 'image'])


def make_df_html(df, columns=None):
    """Helper function to convert dataframe to HTML

    Args:
        df: Pandas dataframe
        columns: list of columns to display

    Returns:
        HTML string
    """
    return df.to_html(escape=False, max_cols=None, columns=columns)


@app.route("/workers")
def view_all_workers():
    """Show all workers who particpated in this HIT"""
    result = df.groupby("WorkerId").agg({'AssignmentId':'count', 'duration':'median', 'time_active_seconds':'median',
                                         'flagged_isObj_as_0':'mean'}).sort_values(by='AssignmentId', ascending=False)
    return make_df_html(result)


@app.route("/workers/<worker_id>")
def view_worker(worker_id):
    """Show the work by this worker"""
    result = df[df["WorkerId"] == worker_id]
    return make_df_html(result)


@app.route("/assignments/<assignment_id>")
def view_assignment(assignment_id):
    """Get the assignment JSON for the given assignment
    TODO decide what to show for individual assignment"""
    a = [a for a in all_assignments if a["Assignment"]["AssignmentId"] == assignment_id]
    assert len(a) == 1
    return jsonify(a[0])


@app.route("/hits")
def view_all_hits_as_list():
    """Show all HITs for the group (NOTE: uses API call to get list of HITs!)"""
    out = []
    hit_ids = get_mturk_hits_for_this_group_id(group_id)
    for hit_id in hit_ids:
        resp = mturk.list_assignments_for_hit(HITId=hit_id)
        out.append([hit_id, len(resp['Assignments']), "<a href=\"/hits/%s\">more</a>" % hit_id,
                    "<a href=\"/mturk/hits/%s\">mturk</a>" % hit_id
                    ])
    return "%s hits<br>" % len(out) + "<br>".join(str(line) for line in out)


@app.route("/result_images/<image_filename>")
def get_image(image_filename):
    """Retrieve the image with this filename

    Uses Flask's send_file function to send the image directly"""
    filepath = os.path.join(RESULT_IMAGE_DIR, image_filename)
    return send_file(filepath)


@app.route("/mturk/hits/<hit_id>")
def get_mturk_info_for_hit(hit_id):
    """Get MTurk assignments JSON for this HIT"""
    return str(mturk.list_assignments_for_hit(HITId=hit_id))


def get_mturk_hits_for_this_group_id(group_id):
    """Get results for all HITs from requester.

    Returns:
        dict mapping each hit_id to its responses
    """
    paginator = mturk.get_paginator('list_hits')
    response_iterator = paginator.paginate()
    hit_ids = []
    for resp in response_iterator:
        print(resp)
        for hit in resp["HITs"]:
            if hit["HITTypeId"] == group_id:
                print("found match:", hit)
                hit_ids.append(hit["HITId"])

    print(len(hit_ids), "hits for typeid=", group_id)
    return hit_ids


@app.route("/hits/<hit_id>")
def view_hit(hit_id):
    """View the results for this HIT.

    Creates HTML with image tags to display each of the annotations submitted"""
    assignments = []
    worker_results = mturk.list_assignments_for_hit(HITId=hit_id)

    for assignment in worker_results['Assignments']:
        response = mturk.get_assignment(
            AssignmentId=assignment['AssignmentId']
        )
        assignments.append(response)

    print(assignments)
    return "%d labels for this hit\n" % len(assignments) + \
           str(["<img src=\"/result_images/worker%s_assignment%s.png\">" %
                (x['Assignment']['WorkerId'], x['Assignment']['AssignmentId'])
                for x in assignments])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8123)
