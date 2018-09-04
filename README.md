
COCO Annotation UI for MyFoodRepo Segmentation Dataset
======================================================

This project includes all the files needed to collect food image segmentations
from MTurk and use these to create a COCO dataset. 
For more details on COCO, please visit [COCO](http://cocodataset.org)

# Main components of this repository
1. Create and upload tasks to MTurk
2. Retrieve the results and view them with the Flask server
3. Create the COCO dataset

# Description of files in this repository

Key files for creating new HITs:
* Static HTML/CSS/JS from COCO-UI: `/static`
* Static content for qualification task (quiz files outside since we want them private, not in S3 folder) `static_qualification`
* XML files for qualification task: Question Form and Answer key `Ques_Form.xml` and `Ans.xml`
* `configs/config_instance_segmentation.json` contains all the MTurk settings (pay, task duration, etc.)
* Segmentation HTML layout is in `tasks/coco_instance_segmentation.html` (interfaces for other image tasks come from the main coco-ui repo) 

Python files
* `create_hit_mturk.py` - key script to upload new segmentation tasks to MTurk. _Be careful with this one!_
* `check_account_balance.py` - "Hello World" script to test the MTurk API.
* `create_coco.py` - creates the COCO dataset from our segmentation annotations
* `get_classnames.py` - helper file for food classes
* `flask_hit_viewer.py` - basic server to view the annotations submitted by crowd workers so far
* `visualize/visualize_annotations.py` - helper file
* `get_results.py` - script to download annotations from MTurk 
* `mturk_api_wrappers.py` - helper functions for interacting with MTurk
* `create_hit.py` - probably broken now, was our Flask app for testing the interface
  
Basic files:
- `.gitignore` - ignore some types of files
- `Procfile` - left from flask app in testing
- `requirements.txt` - Python packages needed for this repository 
- `keys.json` - keep your AWS keys in this file and _make sure these are never publicly available!_

Data folder in directory `data/`
NOTE: these files are created by you or by running the scripts!
* `bad_workers.json` - dictionary of known bad workers and information about what to do with their tasks
* `rejected_assignments.json` - list of assignment IDs that have been rejected
* `hits/<timestamp>_hits.json` - list of the HITs created by running `create_hit_mturk.py`

also in `data/` are the assignment pickles (these are now just JSON lists... excuse the file format):
* `assignments_xxx.pickle`/`flagged_assignments_xxx.pickle` - retrieved assignments from MTurk

Other pickle files in the directory `pickles/`
* important mappings for image IDs to S3 URLs, food101 ID to image IDs, etc.

## OLD SCRATCH WORK/TEAM BRAINSTORMING BELOW THIS LINE

### Adapting to myfoodrepo-segmentation-dataset

COCO steps

large scale dataset to address non-iconic views of (food) objects, contextual reasoning between (food) objects and precise 2D localization of (food) objects.

so our dataset will be bigger than the other papers I've seen where the researchers created their dataset
segmentation models often need domain specific training data for natural images which can be ambiguous (think one food on top of another, or a mix)

fully label and provide segmentation mask for every instance! (otherwise the model will get confused when training)

MTurk-
hierarchical labeling -> is food Y in this image? (supercategories make UI better, breakdown not important)
label, verify, segment the instances

stats we want:
- total instances, images (gonna be ~100k)
- number of labeled instances per food class (> means will help with precise 2D localization models)
- worker hours for each task
- difficulty/cost per task

image ID is key in an S3 bucket that contains the image

### General questions
how will we evaluate quality of worker output (not supposed to "reject" bad work even if we could do it automatically)?

### 1. Category labeling
change wording: select any instance of category X - food Y shown in the image
* what are our categories? (COCO - 91 categories, 11 supercategories)?
    - can/should we just use the folder hierarchy of the images?
    - i.e. "agave agave blah blah blah" - maybe a human readable version
    - or we can sort these ourselves - the basic food groups.
    - The exact breakdown is not that crucial, just helps get better/more complete output from the workers
        * drinks
        * soups
        * sauces
        * composite dishes (cheeseburger?)
        * fruits
        * vegetables
        * seafood
        * meat
        * grains
    - Exclude some things that are not directly edible?
        * raw ingredients like flour, garlic, butter
        * where do we draw the line - powdered sugar on a doughnut, syrup on a waffle, etc.
        
### 2. Instance spotting
locate and mark all instances of food X

If > 10-15 instances marked:

### 3a. Crowd labeling
draw on all unlabeled instances of food X
nice to have: clear/undo

### 3b. Instance segmentation
carefully trace around each region/instance/chunk/pile/?? that contains 100% (?) food X
(problem say with rice if you have a piece of chicken on top in middle = a hole in the trace)

## Comments
* [IMPORTANT] seems like we are mostly trying to learn recurring textures - shapes can be pretty useless for prepared food
    - I think texture lines up fairly well with the breakdown of our dataset...
    - composite dishes: chicken caesar salad we want the output of the segmentation to be...?
        * large "chicken caesar salad" region with fairly high probability
        * contains "romaine lettuce" and "grilled chicken" regions within it
        * we take the biggest of the masks?
    - [TODO] ask users to choose the most applicable category 

* item extends beyond the image - I think this is OK
* training data looks much better than what we actually are eating
    - higher-level motivation again
* undo buttons would be nice
* how "iconic" are our images? Range from a single carrot to a platter with different meat slices, melted stuff, coatings/sauces, etc.
    - this means we need to reconcile what we consider a dish with the way we label stuff
    - stacks/slices
    - mixes
    - glazes
    - shreds
* worker knowledge level
    - batavia, agave, ... complicated ingredients
    - worker location also
* things vs stuff - soup?
* bottles/packaging
* flag as not food
* just the edible part?
* consider - we already sort of know the categories from the way myfoodrepo-images is arranged

## Checklist before launching MTurk task
* We need an instance
* Clear explanation what is needed for task to be approved
* Training tasks
* Test with ourselves
* Feedback testing: connect with Turkers/respond to questions
