import json
import os
import urllib.parse
import pickle
from time import strftime, gmtime
import re
from collections import defaultdict

from bs4 import BeautifulSoup
from jinja2 import FileSystemLoader, Environment
import boto3

from get_classnames import get_all_machine_learn_nodes
from clear_hits_quals import clear_qualifications

# Load config for this task
config = json.load(open("configs/config_instance_segmentation.json"))

# PARAMETERS
URL_OF_S3_IMAGE_DIR = config["IMAGES"]["URL_OF_S3_IMAGE_DIR"]
NUM_BING_IMAGES_PER_CLASS = config["IMAGES"]["NUM_BING_IMAGES_PER_CLASS"]
NUM_FOOD101_IMAGES_PER_CLASS = config["IMAGES"]["NUM_FOOD101_IMAGES_PER_CLASS"]
FRAME_HEIGHT_PIXELS = config["IMAGES"]["FRAME_HEIGHT_PIXELS"]
SAVE_HIT_HTML = True

# Create qualification task with these questions and answers
questions = open('Ques_Form.xml', 'r').read()
answers = open('Ans.xml', 'r').read()

# Build mappings
image_id_to_url = {}
map_bing_id_to_image_ids = defaultdict(list)
map_food_101_id_to_image_ids = defaultdict(list)
all_image_ids = []

HIT = config["HIT"]
if HIT["USE_SANDBOX"]:
    print("create HIT on sandbox")
    endpoint_url = "https://mturk-requester-sandbox.us-east-1.amazonaws.com"
    mturk_form_action = "https://workersandbox.mturk.com/mturk/externalSubmit"
    mturk_url = "https://workersandbox.mturk.com/"
else:
    print("create HIT on mturk")
    input("DOUBLE CHECK THAT YOU ARE READY TO PUSH REAL HITs: PRESS A KEY or STOP NOW!")
    print("OK")
    endpoint_url = "https://mturk-requester.us-east-1.amazonaws.com"
    mturk_form_action = "https://www.mturk.com/mturk/externalSubmit"
    mturk_url = "https://worker.mturk.com/"

# boto3 mturk client
aws_key = json.load(open("keys.json"))

mturk = boto3.client('mturk',
                     aws_access_key_id=aws_key["aws_access_key_id"],
                     aws_secret_access_key=aws_key["aws_secret_access_key"],
                     region_name=HIT["REGION_NAME"],
                     endpoint_url=endpoint_url
                     )

# TODO separate script to upload folder names index to S3 and keep index updated
if os.path.exists("pickles"):
    # Already indexed S3 image IDs
    print("Using existing S3 file index")
    all_image_ids = pickle.load(open("pickles/all_image_ids.pickle", 'rb'))
    image_id_to_url = pickle.load(open("pickles/image_id_to_url.pickle", 'rb'))
    map_food_101_id_to_image_ids = pickle.load(open("pickles/map_food_101_id_to_image_ids.pickle", 'rb'))
    map_bing_id_to_image_ids = pickle.load(open("pickles/map_bing_id_to_image_ids.pickle", 'rb'))
else:
    # Read folder names from S3 bucket. Paginators used since api can list only 1000 at a time.
    # Takes around 2 minutes to get all files
    print("Rebuilding S3 file index")
    s3 = boto3.client('s3', region_name='eu-central-1',
                      aws_access_key_id=aws_key["aws_access_key_id"],
                      aws_secret_access_key=aws_key["aws_secret_access_key"])
    paginator = s3.get_paginator('list_objects')
    operation_parameters = {'Bucket': 'myfoodrepo-bing-images', 'Prefix': 'images'}
    page_iterator = paginator.paginate(**operation_parameters)
    for page in page_iterator:
        print(page)
        for i in page['Contents']:
            splitted = i['Key'].split("/")
            if splitted[0] != 'images':
                continue
            filename = splitted.pop()
            if filename[-4:] != ".jpg":
                # TODO note ASSUMING ALL FILES ARE .jpg so skip this file!!!
                continue
            image_id = filename[:-4]
            classname = "/".join(splitted[1:])
            all_image_ids.append(image_id)
            # image_id_to_class_name[image_id] = classname

            leaf_folder = i['Key'].split("/")[-2]

            # Try to get IDs
            bing_match = re.match("^([0-9]*)\.", leaf_folder)
            if bing_match:
                bing_id = int(bing_match.group(1))
                map_bing_id_to_image_ids[bing_id].append(image_id)

            food_101_match = re.match("^([0-9]*)F_", leaf_folder)
            if food_101_match:
                food_101_id = int(food_101_match.group(1))
                map_food_101_id_to_image_ids[food_101_id].append(image_id)

            filepath_as_url = urllib.parse.quote(os.path.join(classname, filename))
            image_id_to_url[image_id] = "https://s3.eu-central-1.amazonaws.com/myfoodrepo-bing-images/images/" + filepath_as_url

    # NOTE: caching the mappings as pickles
    if not os.path.exists("pickles"):
        os.mkdir("pickles")
    with open("pickles/all_image_ids.pickle", 'wb') as f:
        pickle.dump(all_image_ids, f)
    with open("pickles/image_id_to_url.pickle", 'wb') as f:
        pickle.dump(image_id_to_url, f)
    with open("pickles/map_bing_id_to_image_ids.pickle", 'wb') as f:
        pickle.dump(map_bing_id_to_image_ids, f)
    with open("pickles/map_food_101_id_to_image_ids.pickle", 'wb') as f:
        pickle.dump(map_food_101_id_to_image_ids, f)

print("Number of S3 images available:", len(all_image_ids))


def create_xml_question(html_text):
    """Wrap the given HTML inside an XML object. Uses BeautifulSoup to avoid ParameterValidation Error.

    Args:
        html_text: your HTML code

    Returns:
        XML object ready to be sent to MTurk as question.xml
    """
    return '<HTMLQuestion ' \
           'xmlns="http://mechanicalturk.amazonaws.com/AWSMechanicalTurkDataSchemas/2011-11-11/HTMLQuestion.xsd">' \
           '<HTMLContent><![CDATA[\n' + \
           BeautifulSoup(html_text,'lxml').prettify() + \
           '\n]]></HTMLContent><FrameHeight>%d</FrameHeight></HTMLQuestion>' % FRAME_HEIGHT_PIXELS


hits = {}

qual_HIT = config['QUALIFICATION_HIT']

# TODO shouldn't really be here, clears/disables existing qualification tests!
# if HIT["USE_SANDBOX"]:
#     clear_qualifications(mturk)
#
existing_qualification_tests = mturk.list_qualification_types(Query=qual_HIT["Title"],
                                                              MustBeRequestable=True,
                                                              MustBeOwnedByCaller=True)
assert existing_qualification_tests['NumResults'] < 2, "somehow have duplicate qualification types (naming issues?)"

if existing_qualification_tests['NumResults'] == 0:
    qual_response = mturk.create_qualification_type(Name=qual_HIT["Title"],
                                                    Keywords=qual_HIT["Keywords"],
                                                    Description=qual_HIT["Description"],
                                                    QualificationTypeStatus='Active',
                                                    Test=questions,
                                                    AnswerKey=answers,
                                                    TestDurationInSeconds=qual_HIT["TestDurationInSeconds"])
    assert qual_response['ResponseMetadata']['HTTPStatusCode'] == 200
else:
    qualification_type_id = existing_qualification_tests['QualificationTypes'][0]['QualificationTypeId']
    qual_response = mturk.update_qualification_type(QualificationTypeId=qualification_type_id,
                                                    Description=qual_HIT["Description"],
                                                    QualificationTypeStatus='Active',
                                                    Test=questions,
                                                    AnswerKey=answers,
                                                    TestDurationInSeconds=qual_HIT["TestDurationInSeconds"])
    assert qual_response['ResponseMetadata']['HTTPStatusCode'] == 200
    # TODO does this force anyone that had the qualification before to re-qualify? OR update their qualification?
qualification_type_id = qual_response['QualificationType']['QualificationTypeId']

# Create 1 HIT for each image in each class

# TODO if using the same images as before
# for image_id in image_ids_to_use:
#     class_id = map_image_id_to_class[image_id]
# previous_hits = json.load(open("hits/2018_07_12_16:26:01_hits.json"))
# previous_image_ids_used = []
# for hit, hit_info in previous_hits.items():
#     image_id = hit_info["IMAGE_ID"]
#     previous_image_ids_used.append(image_id)

# Retrieve metadata for classes from MyFoodRepo graph
map_class_id_to_node = get_all_machine_learn_nodes()

# class_ids_to_use = config["IMAGES"]["CLASS_IDS_TO_USE"]
# Choose images to label: use all Food101 classes marked as suitable for machine learning
class_ids_to_use = []
for class_id, node in map_class_id_to_node.items():
    if 'food_101' in node and node.get('should_machine_learn', False):
        class_ids_to_use.append(class_id)

print("Classes to use:", len(class_ids_to_use), class_ids_to_use)

total_num_images = 0
for class_id in class_ids_to_use:
    node = map_class_id_to_node[class_id]  # JSON with names, dataset ids, etc.

    # Get metadata needed for mTurk task
    display_name = node['display_name_translations']['en']
    search_query = node['search_terms']

    # Get the image IDs
    bing_images = []
    if 'bing_crawl_2017' in node:
        bing_images.extend(map_bing_id_to_image_ids[node['bing_crawl_2017']])

    food_101_images = []
    if 'food_101' in node:
        food_101_images.extend(map_food_101_id_to_image_ids[node['food_101']])

    print("Number of images for class", display_name, class_id, ": bing=", len(bing_images), "food101=", len(food_101_images))

    # Create hits with the first X bing images and first Y food101 images
    image_ids_to_use_for_this_class = bing_images[:NUM_BING_IMAGES_PER_CLASS] + food_101_images[:NUM_FOOD101_IMAGES_PER_CLASS]
    # # TODO if reusing same images as previous experiment
    # image_ids_to_use_for_this_class = [image_id for image_id in previous_image_ids_used
    #                                    if image_id in bing_images or image_id in food_101_images]
    print(len(image_ids_to_use_for_this_class), "images will be used for class", class_id)
    total_num_images += len(image_ids_to_use_for_this_class)

    # Loop through the images folder for this class
    for image_id in image_ids_to_use_for_this_class:  # TODO only using some images per class right now during testing
        image_url = image_id_to_url[image_id]

        # Use this dict to fill the HTML template
        temp_dict = {
            "IMAGE_ID": image_id,
            "IMAGE_URL": image_url,
            "CLASS_NAME": display_name,
            "SEARCH_QUERY": search_query,
            "TIME_CREATED_DEBUG": strftime("%Y_%m_%d_%H:%M:%S ", gmtime())
        }
        print(temp_dict)

        # Template stored in tasks/
        template_dir_loader = FileSystemLoader('tasks')
        env = Environment(loader=template_dir_loader)
        template = env.get_template("coco_instance_segmentation.html")

        # Generate HTML text from jinja2 templates
        output_html = template.render(STATIC_ROOT=config["STATIC_ROOT"],
                                      MTURK_FORM_TO_SUBMIT=mturk_form_action,
                                      image_to_annotate=temp_dict,
                                      max_count=2)

        html_text = output_html.replace("../static", config["STATIC_ROOT"])

        # Save HIT page HTML for debugging
        if SAVE_HIT_HTML:
            if not os.path.exists("debug"):
                os.mkdir("debug")
            with open('debug/hit_%s.html' % image_id, 'w') as f:
                f.write(html_text)

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
            QualificationRequirements=[{'QualificationTypeId': qualification_type_id,
                                        'Comparator': 'EqualTo',
                                        'IntegerValues': [100]},
                                       ]
        )

        # print(new_hit)
        print("HITId: " + new_hit['HIT']['HITId'])
        print("A new HIT has been created. You can preview it here:")
        print(mturk_url + "mturk/preview?groupId=" + new_hit['HIT']['HITGroupId'])
        temp_dict['HITId'] = new_hit['HIT']['HITId']
        for key in new_hit['HIT'].keys():
            temp_dict[key] = new_hit['HIT'][key]
        hits[new_hit['HIT']['HITId']] = temp_dict

print(total_num_images, "total images to create HITs for")
print("Created", len(hits), "hits")

hits_filename = "hits/" + strftime("%Y_%m_%d_%H:%M:%S_", gmtime()) + "hits.json"
if not os.path.exists("hits"):
    os.mkdir("hits")
with open(hits_filename, 'w') as f:
    # HIT details saved with Time Stamps.
    json.dump(hits, f, indent=4, sort_keys=True, default=str)
    print("Saved hits file:", hits_filename)
