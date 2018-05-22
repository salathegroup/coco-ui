import json
import os
import random
import urllib.parse
import uuid
import sys

from jinja2 import FileSystemLoader
import boto3

from flask import Flask, request, render_template, jsonify, redirect, url_for
app = Flask("test segmentation task MTurk")

images_dir = sys.argv[1]  # TODO use flask app.config

# Small set of images for testing

# Build mapping
image_id_to_class_name = {}
image_id_to_url = {}

# TODO only want a small set of random images right now
all_image_ids = []
for file_dir, _, files in os.walk(images_dir):
    for filename in files:
        if filename.endswith(".jpg"):
            image_id = filename[:-4]
            print(image_id)

            # TODO remove, this keeps ~0.1% of the 125k images so that it's possible to compare annotations
            # if random.random() > 0.001:
            #     continue

            all_image_ids.append(image_id)

            # Get the class directory
            class_dir = os.path.relpath(file_dir, images_dir)
            print(class_dir)
            image_id_to_class_name[image_id] = class_dir

            # Get the S3 static URL for this image
            filepath_as_url = urllib.parse.quote(os.path.join(class_dir, filename))
            image_id_to_url[image_id] = "https://s3.eu-central-1.amazonaws.com/myfoodrepo-bing-images/images/" + filepath_as_url

            print(image_id, image_id_to_class_name[image_id], image_id_to_url[image_id])


print("Number of images available:", len(all_image_ids))


def create_xml_question(html_text):
    """Wrap the given HTML inside an XML object.

    Args:
        html_text: your HTML code

    Returns:
        XML object ready to be sent to MTurk as question.xml
    """
    return '<HTMLQuestion ' \
           'xmlns="http://mechanicalturk.amazonaws.com/AWSMechanicalTurkDataSchemas/2011-11-11/HTMLQuestion.xsd">' \
           '<HTMLContent><![CDATA[\n' + \
           html_text + \
           '\n]]></HTMLContent><FrameHeight>600</FrameHeight></HTMLQuestion>'


@app.route('/routes', methods=['GET'])
def get_routes():
    endpoints = [rule.rule for rule in app.url_map.iter_rules()
                 if rule.endpoint != 'static']
    return jsonify(dict(api_endpoints=endpoints))


@app.route("/annotations/<image_id>", methods=['GET'])
def get_form(image_id):
    # # Get path for stored annotation for this image
    # if os.path.exists(os.path.join(ANNOTATION_DIR, image_id)):
    return "GET request for image_id = %s???" % image_id


@app.route("/")
def main_page():
    doc = """
    <h1>Help page under construction<h1>
    
    See all available endpoints: <a href="/routes">here</a>
    
    """
    return doc


@app.route("/segment/submit", methods=['POST'])
def process_submission():
    """Add annotations for image(s?)"""
    form = request.form
    print(form)

    # TODO for debug, save annotation with ImageID and AssignmentID probably
    # for now, just save the form
    annotations_dir = "annotations"
    os.makedirs(annotations_dir, exist_ok=True)
    filename = os.path.join(annotations_dir, "%s.json" % uuid.uuid4())
    with open(filename, 'w') as f:
        json.dump(request.form, f)

    if form['isObj'] == '1':
        print(form["ans"])
        ans = json.loads(form["ans"])
        annotations = json.loads(ans["results"])  # JSON response was escaped
        print(annotations)
        print(type(annotations))
        image_ids = list(annotations.keys())  # list of images with new annotations
        assert len(image_ids) == 1
        output = "SUBMITTED ANNOTATION FOR IMAGE %s" % str(image_ids)
    else:
        output = "FLAGGED IMAGE AS NOT CONTAINING THE CLASS"

    return output + "<br><a href=\"/segment/random\">Label another image</a>"


@app.route("/segment/random")
def segment_random_image():
    """INSTEAD OF CREATING HIT ON MTURK, RETURN HTML SO THAT USER CAN DO TASK LOCALLY

    # TODO get a random imageID, retrieve its static URL and get the class name from this?
    """
    image_id = random.choice(all_image_ids)
    dest = url_for("segment_image", image_id=image_id)
    print(dest)

    return redirect(dest)


@app.route("/segment/<image_id>")
def segment_image(image_id):
    """Segment a specific image"""
    image_url = image_id_to_url[image_id]
    class_name = image_id_to_class_name[image_id]

    # Load config for this task
    config = json.load(open("config.json"))

    # When creating HITs we can generate this metadata from the images directory paths
    image = {
        "IMAGE_ID": image_id,
        "IMAGE_URL": image_url,
        "CLASS_NAME": class_name
    }
    print(image)

    mturk_form_action = "/segment/submit"

    # Template stored in tasks/
    template_dir_loader = FileSystemLoader('tasks')
    app.jinja_loader = template_dir_loader
    output_html = render_template("coco_instance_segmentation.html",
                                  STATIC_ROOT=config["STATIC_ROOT"],
                                  MTURK_FORM_TO_SUBMIT=mturk_form_action,
                                  image_to_annotate=image,
                                  max_count=999999999)
    # print(output_html)
    return output_html

    # # Fill in the question template with the correct URLs
    # html_text = open(HIT["Question"], "r").read()
    # html_text.replace("../static", config["STATIC_ROOT"])
    # html_text = html_text.replace("MTURK_FORM_TO_SUBMIT", mturk_form_action)
    #
    # # TODO For each image fill in the name field and image URL
    # html_text = html_text.replace("PHOTO_ID", image_id)
    #
    # instance_name = "?apple?"
    # # TODO find name from directory
    # html_text = html_text.replace("PHOTO_INSTANCE_NAME", instance_name)
    # image_url = "https://www.giallozafferano.it/images/ricette/174/17464/foto_hd/hd450x300.jpg"
    # html_text = html_text.replace("PHOTO_URL", image_url)
    #
    # print(html_text)
    # return html_text


def create_instance_segmentation_hit():
    """CREATE MTURK (Sandbox?) HIT # TODO needs to call the HTML generation code for a specific image, so refactor"""
    if not os.path.exists("keys.json"):
        raise FileNotFoundError('AWS keys should be stored in keys.json')

    # Load AWS keys from JSON
    aws_key = json.load(open("keys.json"))

    # Load config for this task
    config = json.load(open("configs/config_instance_segmentation.json"))

    HIT = config["HIT"]
    if HIT["USE_SANDBOX"]:
        print("create HIT on sandbox")
        endpoint_url = "https://mturk-requester-sandbox.us-east-1.amazonaws.com"
        mturk_form_action = "https://workersandbox.mturk.com/mturk/externalSubmit"
        mturk_url = "https://workersandbox.mturk.com/"
    else:
        print("create HIT on mturk")
        endpoint_url = "https://mturk-requester-sandbox.us-east-1.amazonaws.com"  # TODO still sandbox only for now
        mturk_form_action = "https://www.mturk.com/mturk/externalSubmit"
        mturk_url = "https://worker.mturk.com/"

    # Create mturk connection through boto3
    mturk = boto3.client('mturk',
                         aws_access_key_id=aws_key["aws_access_key_id"],
                         aws_secret_access_key=aws_key["aws_secret_access_key"],
                         region_name=HIT["REGION_NAME"],
                         endpoint_url=endpoint_url
                         )

    new_hit = mturk.create_hit(
        Title=HIT['Title'],
        Description=HIT["Description"],
        Keywords=HIT["Keywords"],
        Reward=HIT["Reward"],
        MaxAssignments=HIT["MaxAssignments"],
        LifetimeInSeconds=HIT["LifetimeInSeconds"],
        AssignmentDurationInSeconds=HIT["AssignmentDurationInSeconds"],
        AutoApprovalDelayInSeconds=HIT["AutoApprovalDelayInSeconds"],
        Question=create_xml_question(html_text),
    )
    print("HITId: " + new_hit['HIT']['HITId'])
    print("A new HIT has been created. You can preview it here:")
    print(mturk_url + "mturk/preview?groupId=" + new_hit['HIT']['HITGroupId'])


def usage():
    print("Must provide local image directory as a command line argument in order to create example tasks")


if __name__ == "__main__":
    usage()
    app.run(host="0.0.0.0")
