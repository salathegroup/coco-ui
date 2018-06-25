import json
import os
import random
import urllib.parse
import uuid
import sys
from bs4 import BeautifulSoup
from jinja2 import FileSystemLoader, Environment
import boto3
import re
from time import strftime, gmtime
#from flask import Flask, request, render_template, jsonify, redirect, url_for


#images_dir = sys.argv[1] if len(sys.argv) > 1 else '/home/harsh/data/fresh-sf/images' # TODO use flask app.config

# Small set of images for testing

# Build mapping
image_id_to_class_name = {}
image_id_to_url = {}


#OPtion to use flask app on heroku for getting HITs
def create_external_question(image_id):
    return '<?xml version="1.0" encoding="UTF-8"?>'\
        '<ExternalQuestion xmlns="http://mechanicalturk.amazonaws.com/AWSMechanicalTurkDataSchemas/2006-07-14/ExternalQuestion.xsd">'\
        '<ExternalURL>https://thafack2.herokuapp.com/segment/random</ExternalURL>'\
            '<FrameHeight>1000</FrameHeight>'\
        '</ExternalQuestion>'\


#Cleaning Classnames
def clean_names(name):
    if type(name.split("/")) == list:
        text = " -- ".join(name.split("/"))
    else:
        text = name
    text = text.replace(".","_")    
    text = re.sub('[0-9]+\w*_','',text)
    text = text.replace("_","")
    return text
 
def replace_static_root(htmssa,static_root):
	return htmssa.replace("../static",static_root)
# TODO only want a small set of random images right now
all_image_ids = []

#Reading folder names from S3 bucket. paginators used since api can list only 1000 at a time.
#Takes around 2 minutes to get all files

s3 = boto3.client('s3',region_name='eu-central-1')
paginator = s3.get_paginator('list_objects')
operation_parameters = {'Bucket':'myfoodrepo-bing-images','Prefix':'images'}
page_iterator = paginator.paginate(**operation_parameters)
for page in page_iterator:
    for i in page['Contents']:
        splitted = i['Key'].split("/")
        if splitted[0] != 'images':
            continue
        filename = splitted.pop()
        image_id = filename[:-4]     
        classname = "/".join(splitted[1:])
        all_image_ids.append(image_id)
        image_id_to_class_name[image_id] = classname
        filepath_as_url = urllib.parse.quote(os.path.join(classname, filename))
        image_id_to_url[image_id] = "https://s3.eu-central-1.amazonaws.com/myfoodrepo-bing-images/images/" + filepath_as_url
print("Number of images available:", len(all_image_ids))


#Use local image directory to get class names . (Faster)
def use_local_imdir():
    images_dir = sys.argv[1]  # TODO use flask app.config

    
    for file_dir, _, files in os.walk(images_dir):
        for filename in files:
            if filename.endswith(".jpg"):
                image_id = filename[:-4]

                all_image_ids.append(image_id)

                # Get the class directory
                class_dir = os.path.relpath(file_dir, images_dir)

                # TODO consistent way to extract label from directory name
                # some are enclosed in quotes xxx. "avocado" avocado...
                # whereas others are not quoted
                classname = class_dir

                image_id_to_class_name[image_id] = classname

            # Get the S3 static URL for this image
                filepath_as_url = urllib.parse.quote(os.path.join(class_dir, filename))
                image_id_to_url[image_id] = "https://s3.eu-central-1.amazonaws.com/myfoodrepo-bing-images/images/" + filepath_as_url

            # print(image_id, image_id_to_class_name[image_id], image_id_to_url[image_id])
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
           BeautifulSoup(html_text,'lxml').prettify() + \
           '\n]]></HTMLContent><FrameHeight>600</FrameHeight></HTMLQuestion>'

#Need BeautifulSoup to avoid ParameterValidation Error.




def segment_image(image_id):
#   Segment a specific image
    image_url = image_id_to_url[image_id]
    class_name = image_id_to_class_name[image_id]

    # Load config for this task
    config = json.load(open("configs/config_instance_segmentation.json"))

    # When creating HITs we can generate this metadata from the images directory paths
    image = {
        "IMAGE_ID": image_id,
        "IMAGE_URL": image_url,
        "CLASS_NAME": class_name
    }
    print(image)

    mturk_form_action = "https://workersandbox.mturk.com/mturk/externalSubmit"

    # Template stored in tasks/
    template_dir_loader = FileSystemLoader('tasks')
    env = Environment(loader=template_dir_loader)
    template = env.get_template("coco_instance_segmentation.html")	
    #Generate html text from jinja2 templates
    output_html = template.render(STATIC_ROOT=config["STATIC_ROOT"],
                                  MTURK_FORM_TO_SUBMIT=mturk_form_action,
                                  image_to_annotate=image,
                                  max_count=2)
    # print(output_html)
    output_html =replace_static_root(output_html,config["STATIC_ROOT"]) 	
    f = open('tasks/outtpit.html','w')#HTML files saved locally for easy debugging
    f.write(output_html)
    f.close()		
    return image

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
    
    #qual_image_ids = random.sample(all_image_ids,2)
    #qual_img = random.choice(qual_image_ids)
    #qual_specs  = segment_image(qual_img)
    
    #boto3 mturk client
    mturk = boto3.client('mturk',
                         aws_access_key_id=aws_key["aws_access_key_id"],
                         aws_secret_access_key=aws_key["aws_secret_access_key"],
                         region_name=HIT["REGION_NAME"],
                         endpoint_url=endpoint_url
                         )
    
    
    #Failed try to create Custom QualificationType using externalQuestion/HTMLQuestion
    #Run into ParameterValidation Error
    #qual=mturk.create_qualification_type(Name='Segmentation Qualification Task',
    #                                Description='As the name suggests',
    #                                QualificationTypeStatus='Active',
    #                                Keywords='segmentation',
    #                                Test = open('Ques_Form.xml','r').read(),
    #                                TestDurationInSeconds = 120
    #                                )
    


    #Uncomment below lines to create a new Qualification Type (Unique Name required)
    #questions = open('Ques_Form.xml','r').read()
    #answers = open('Ans.xml','r').read()
    #qual_response = mturk.create_qualification_type(Name='Color blindness test 1a',Keywords='test, qualification, sample, colorblindness, boto',Description='This is a brief colorblindness test',QualificationTypeStatus='Active',Test=questions,AnswerKey=answers,TestDurationInSeconds=300)
    #print ("Qualification Type Id:")
    #print (qual_response['QualificationType']['QualificationTypeId'])                              
    sample_length = config.sample_length
    image_id = random.sample(all_image_ids,sample_length)
    #Randomly sampling a sample_length size array of image_id(s)
    hits = {}    
    for i in image_id:
        temp_dict=segment_image(i)
    # Create a hit for each sampled image_id
        html_text = open('tasks/outtpit.html',"r").read() 
    
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

#            Question=create_external_question(i),
#            QualificationRequirements=[{'QualificationTypeId':qual_response['QualificationType']['QualificationTypeId'],
#            'Comparator':'EqualTo',
#            'IntegerValues':[100]}]
        )
#Above lines to be uncommented for encforcing qualification in the HIT        
        print("HITId: " + new_hit['HIT']['HITId'])
        print("A new HIT has been created. You can preview it here:")
        print(mturk_url + "mturk/preview?groupId=" + new_hit['HIT']['HITGroupId'])
        temp_dict['HITId'] = new_hit['HIT']['HITId']
        for key in new_hit['HIT'].keys():
            temp_dict[key] = new_hit['HIT'][key]
        hits[new_hit['HIT']['HITId']] = temp_dict

    with open("hits/"+ strftime("%Y_%m_%d_%H:%M%S ",gmtime()) + "hits.json",'w') as f:
        json.dump(hits,f,indent=4, sort_keys=True, default=str)
#HIT details saved with Time Stamps.

def usage():
    print("Must provide local image directory as a command line argument in order to create example tasks")


if __name__ == "__main__":
    create_instance_segmentation_hit() 



