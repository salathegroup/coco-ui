"""
Create COCO format dataset from the given MTurk assignments.

See below as there are many files involved with the assignment data and information we might have
collected regarding bad workers etc.

Warnings:
- this will break with Bing images since full res are in another folder!!!
- Bing images will also break the food graph category ID mapping function
"""
import pickle

import xmltodict

import json
import re
import tqdm
from PIL import Image

from pycocotools.coco import COCO
import skimage.io as io
import matplotlib.pyplot as plt
import os

from get_classnames import get_food_graph


IMAGES_FOLDER_PATH="/mount/SDB/myfoodrepo-seth/myfoodrepo-images/images"
# ANNOTATIONS_PATH="/mount/SDB/myfoodrepo-seth/prepared_annotations/coco_annotations_assignments_2018_08_02_14-29-36.json"

assignment_filenames = [
    "assignments_2018_08_09_11:55:07.pickle", # round 2 of data collection 11.6k HITs
    "assignments_2018_08_02_14:29:36.pickle" # round 1 of data collection 11.8k HITs
]
flagged_assignment_filenames = [
    "flagged_assignments_2018_08_09_11:55:07.pickle", # round 2 of data collection 11.6k HITs
    "flagged_assignments_2018_08_02_14:29:36.pickle" # round 1 of data collection 11.8k HITs
]

bad_workers = [wid for wid, worker_dict in json.load(open("bad_workers.json")).items()
               if worker_dict["block_all"]]
ok_workers = []
print(len(bad_workers), "bad workers that will be blocked")

# Get rejected assignments list
rejected_assignments = json.load(open("rejected_assignments.json"))
print("Found", len(rejected_assignments), "specific rejected assignments")

OUTPUT_DIRECTORY = "/mount/SDB/myfoodrepo-seth/prepared_annotations/data"

TRAIN_PERCENT = 0.8
VAL_PERCENT = 0.1
TEST_PERCENT = 1 - (TRAIN_PERCENT + VAL_PERCENT)


# Build index of image_id to filepath
image_path_map = {}
rootDir = IMAGES_FOLDER_PATH
for dirName, subdirList, fileList in tqdm.tqdm(os.walk(rootDir, topdown=False)):
    for fname in fileList:
        if len(re.findall("^\d+.jpg$", fname))>0:
            #print('.', end='', flush=True)
            image_path_map[fname.replace(".jpg", "")] = os.path.join(dirName, fname)


def generate_mapping_image_id_to_category_id():
    """Create a mapping from each image ID used to its category (food class) ID.

    Returns:
        dict: mapping from image ID to food class ID
    """
    pickle_path = "pickles/map_image_id_to_category_id.pickle"
    if os.path.exists(pickle_path):
        map_image_id_to_category_id = pickle.load(open(pickle_path, 'rb'))
    else:
        # Build mapping
        map_image_id_to_category_id = dict()

        # Assumes existence of other pickles
        # map_bing_id_to_image_ids = pickle.load(open("pickles/map_bing_id_to_image_ids.pickle", 'rb'))
        map_food_101_id_to_image_ids = pickle.load(open("pickles/map_food_101_id_to_image_ids.pickle", 'rb'))

        # Build mapping of bing or food101 id to our category id
        # map_bing_id_to_category_id = {}
        map_food_101_id_to_category_id = {}
        graph = get_food_graph()
        # key_bing = 'bing_crawl_2017'
        key_food_101 = 'food_101'
        for node in graph['nodes']:
            # if key_bing in node:
            #     assert node[key_bing] not in map_bing_id_to_category_id, "Assuming Bing IDs map to a single category in food graph %s" % node
            #     map_bing_id_to_category_id[node[key_bing]] = node["id"]
            if key_food_101 in node:
                assert node[key_food_101] not in map_food_101_id_to_category_id, "Assuming food101 IDs map to a single category in food graph %s" % node
                map_food_101_id_to_category_id[node[key_food_101]] = node["id"]

        # print(len(map_bing_id_to_category_id), "bing ids in graph")
        print(len(map_food_101_id_to_category_id), "food101 ids in graph")
        #
        # for bing_id, image_ids in map_bing_id_to_image_ids.items():
        #     if bing_id not in map_bing_id_to_category_id:
        #         print("Warning: Bing ID", bing_id, "no longer in food graph, skipping!!!")
        #         continue
        #
        #     category_id = map_bing_id_to_category_id[bing_id]
        #     for image_id in image_ids:
        #         assert image_id not in map_image_id_to_category_id, "Image ID %s already exists in mapping ??? Should be unique" % image_id
        #         map_image_id_to_category_id[image_id] = category_id

        for food_101_id, image_ids in map_food_101_id_to_image_ids.items():
            if food_101_id not in map_food_101_id_to_category_id:
                print("Warning: Food101 ID", food_101_id, "no longer in food graph, skipping!!!")
                continue

            category_id = map_food_101_id_to_category_id[food_101_id]
            for image_id in image_ids:
                assert image_id not in map_image_id_to_category_id, "Image ID %s already exists in mapping ??? Should be unique" % image_id
                map_image_id_to_category_id[image_id] = category_id

        # Save pickle
        print(len(map_image_id_to_category_id), "image ids in mapping image_id -> category_id")
        pickle.dump(map_image_id_to_category_id, open(pickle_path, 'wb'))

    return map_image_id_to_category_id


map_image_id_to_category_id = generate_mapping_image_id_to_category_id()


def get_category_id_from_image_id(image_id):
    """Find Food Graph class ID from image ID"""
    return map_image_id_to_category_id[image_id]


def get_annotation(a):
    """From assignment JSON, create annotation in COCO format

    Returns:
        (image_info, coco_annotation):
        tuple of (dict of metadata for the image corresponding to this annotation, coco format annotation as a dict)
    """
    xml_doc = xmltodict.parse(a['Answer'])
    isObj = None
    ans = None
    for ans in xml_doc['QuestionFormAnswers']['Answer']:
        if ans['QuestionIdentifier'] == 'isObj':
            isObj = int(ans['FreeText'])
        if ans['QuestionIdentifier'] == "ans":
            ans = json.loads(ans['FreeText'])

    if isObj == 0:
        return None, None
    else:
        results = json.loads(ans["results"])
        assert len(results) == 1  # should be 1 image per task
        image_id, annotations = results.popitem()

        # TODO lookup food graph class ID from image_id
        category_id = get_category_id_from_image_id(image_id)

        annotation_id = a['AssignmentId']  # TODO if multiple annotations for same image...?
        # TODO ids are strings
        # TODO category ID could/should be the class name of the food

        # Get image information
        image_info_from_action_log = json.loads(ans['action_log'])[0]

        photo_url = image_info_from_action_log['photo_url']

        from PIL import Image
        im = Image.open(image_path_map[image_id])

        width, height = im.size

        annotations_in_pixels = []
        for poly in annotations:
            # Create real x,y points for the image
            # from coco_instance_segmentation.html comment:
            # polygon: [x1,y1,x2,y2,...,xn,yn] x, y are fractions of image width and height
            poly_in_pixels = [
                coord * width if i % 2 == 0 else coord * height
                for i, coord in enumerate(poly)
            ]

            annotations_in_pixels.append(poly_in_pixels)

        coco_annotation = {
            'id': annotation_id,
            'image_id': image_id,
            'segmentation': annotations_in_pixels,
            'category_id': category_id,
        }  # not filling in: area, bbox, iscrowd

        image_info = {
            'id': image_id,
            'filename': photo_url,
            'width': width,
            'height': height
        }

        assert image_info['id'] == image_id

        return image_info, coco_annotation


def produce_annotations_from_assignment_pickle():
    """Extract annotations from the pickle that has the list of assignment JSON objects

    Uses the '[flagged_]assignment_filenames' global variables!

    Returns:
        a list of the COCO annotations from these assignments
        (each is a dict with 'id', 'image_id', 'segmentation', 'category_id' and perhaps other keys)
    """
    all_assignments = []
    for assignment_filename in assignment_filenames:
        all_assignments.extend(pickle.load(open(assignment_filename, 'rb')))
    print(len(all_assignments), "assignments in all assignment pickle files")

    flagged_assignments = []
    for flagged_filename in flagged_assignment_filenames:
        flagged_assignments.extend(pickle.load(open(flagged_filename, 'rb')))
    print(len(flagged_assignments), "flagged assignments in all assignment pickle files")

    rejected_assignments_set = set(rejected_assignments)

    flagged_workers = set(bad_workers + ok_workers)

    # TODO should always only use approved assignments
    input("Check that these assignments have been approved (and rejected ones filtered out)")

    coco_annotations = []
    for i, assignment in enumerate(all_assignments):
        if i % 100 == 0:
            print(i, "assignments processed so far")

        assignment_id = assignment['Assignment']['AssignmentId']
        worker_id = assignment['Assignment']['WorkerId']

        if assignment_id in flagged_assignments or assignment_id in rejected_assignments_set or worker_id in flagged_workers:
            print("Skipping flagged/rejected assignment %s by worker %s" % (assignment_id, worker_id))
            continue

        image_info, coco_annotation = get_annotation(assignment['Assignment'])
        if coco_annotation is None:
            continue
        coco_annotations.append(coco_annotation)

    return coco_annotations


annotations = produce_annotations_from_assignment_pickle()
print(len(annotations), "annotations file")

# Index annotations by image_id
annotations_by_image_id = {}
for item in annotations:
    try:
        annotations_by_image_id[item["image_id"]].append(item)
    except:
        annotations_by_image_id[item["image_id"]] = [item]


# Split into train/val/test datasets

images_in_annotations = list(annotations_by_image_id.keys())
print(images_in_annotations)
random.shuffle(images_in_annotations)

TRAIN_IDX = int(len(images_in_annotations) * TRAIN_PERCENT)
VAL_IDX = TRAIN_IDX + int(len(images_in_annotations) * VAL_PERCENT)
TEST_IDX = len(images_in_annotations)

TRAIN_IMAGES = images_in_annotations[0:TRAIN_IDX]
VAL_IMAGES = images_in_annotations[TRAIN_IDX:VAL_IDX]
TEST_IMAGES = images_in_annotations[VAL_IDX:TEST_IDX]
print("Train images", len(TRAIN_IMAGES))
print("Val images", len(VAL_IMAGES))
print("Test images", len(TEST_IMAGES))


def generate_image_object(_image, IMAGES_DIR):
    """Generate the image object dict (file_name, width, height, id) for this image"""
    image_path = image_path_map[_image]
    target_filename = "{}.jpg".format(_image.zfill(12))
    _image_object = {}
    _image_object["id"] = int(_image)
    _image_object["file_name"] = target_filename
    im = Image.open(image_path)
    width, height = im.size
    _image_object["width"] = width
    _image_object["height"] = height
    im.save(os.path.join(IMAGES_DIR, target_filename))
    im.close()
    return _image_object


def get_categories_from_food_graph(category_ids):
    """Retrieve category information from food graph DB for the classes used in this dataset"""
    graph = get_food_graph()

    category_ids = set(category_ids)

    return [{'id': node['id'], 'name': node['display_name_translations']['en'], 'supercategory': 'food'}
            for node in graph['nodes']
            if node['id'] in category_ids]

    
def generate_annotations_file(IMAGES, OUTPUT_DIRECTORY):
    """Generate annotations.json file for this dataset

    Args:
        IMAGES: image IDs for this dataset
        OUTPUT_DIRECTORY: output directory for this dataset
    """
    d = {}
    d["info"] = {'contributor': 'sv', 'about': 'My Food Repo dataset', 'date_created': '08/09/2018', 'description': 'Annotations on myfoodrepo dataset', 'version': '1.0', 'year': 2018}
    # NOTE "categories" created by checking all category IDs used in this dataset
    category_ids_in_this_dataset = set()

    d["images"] = []
    d["annotations"] = []
    
    IMAGES_DIR = os.path.join(OUTPUT_DIRECTORY, "images")
    if not os.path.exists(IMAGES_DIR):
        os.makedirs(IMAGES_DIR)
    
    annotation_count = 0
    for _image in tqdm.tqdm(IMAGES):
        try:
            image_path = image_path_map[_image]
        except:
            print("Error Processing : ", _image)
            continue
        
        _image_object = generate_image_object(_image, IMAGES_DIR)
        assert _image_object != None
        d["images"].append(_image_object)
        for _annotation in annotations_by_image_id[_image]:
            _annotation["id"] = annotation_count
            annotation_count += 1
            _annotation["image_id"] = int(_image)
            d["annotations"].append(_annotation)
            category_ids_in_this_dataset.add(_annotation["category_id"])

    d["categories"] = get_categories_from_food_graph(category_ids_in_this_dataset)
    print(len(d["categories"]), "categories")

    fp = open(os.path.join(OUTPUT_DIRECTORY, "annotations.json"), "w")
    fp.write(json.dumps(d))
    fp.close()
    print(len(d["images"]), "images")
    print(d["images"][0])


def test_annotations(subdir_name):
    """
    Test if the annotations work properly
    """
    IMAGES_DIRECTORY = "../data/{subdir_name}/images".format(subdir_name=subdir_name)
    ANNOTATIONS_PATH = "../data/{subdir_name}/annotations.json".format(subdir_name=subdir_name)
    
    coco = COCO(ANNOTATIONS_PATH)
    category_ids = coco.loadCats(coco.getCatIds())
    print(category_ids)
    image_ids = coco.getImgIds(catIds=coco.getCatIds())
    random_image_id = random.choice(image_ids)
    img = coco.loadImgs(random_image_id)[0]
    print(img)
    image_path = os.path.join(IMAGES_DIRECTORY, img["file_name"])
    I = io.imread(image_path)
    
    annotation_ids = coco.getAnnIds(imgIds=img['id'])
    annotations = coco.loadAnns(annotation_ids)
    plt.imshow(I); plt.axis('off')
    coco.showAnns(annotations)


if __name__ == "__main__":
    generate_annotations_file(TRAIN_IMAGES, os.path.join(OUTPUT_DIRECTORY, "myfoodrepo-train"))
    generate_annotations_file(VAL_IMAGES, os.path.join(OUTPUT_DIRECTORY, "myfoodrepo-val"))
    generate_annotations_file(TEST_IMAGES, os.path.join(OUTPUT_DIRECTORY, "myfoodrepo-test"))
    # test_annotations("myfoodrepo-train")
    # test_annotations("myfoodrepo-val")
    # test_annotations("myfoodrepo-test")
