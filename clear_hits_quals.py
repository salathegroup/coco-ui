"""Brute force way to clear hits & qualifications while debugging"""
import json
import datetime

import boto3


def clear_qualifications(mturk):
    """DANGER: deletes all the qualifications we've created as well as all the HITs that we can delete"""
    print("Warning: calling clear_qualifications")
    resp = mturk.list_qualification_types(MustBeRequestable=False, MustBeOwnedByCaller=True)
    print("Qualification types to delete:", resp)
    # TODO note deleting all existing qualification tasks
    for qt in resp['QualificationTypes']:
        delq_resp = mturk.delete_qualification_type(QualificationTypeId=qt['QualificationTypeId'])
        print("Delete qualification type response:", delq_resp)


def clear_all_hits(mturk):
    """DANGER: deletes HITS! TODO doesn't seem to delete all for some reason, Amazon api is annoying"""
    # TODO NOTE deleting all existing hits!!!
    print("Warning: clearing all hits, mturk=")
    our_hits = mturk.list_hits()['HITs']
    for hit in our_hits:
        print(hit)
        update_resp = mturk.update_expiration_for_hit(HITId=hit['HITId'], ExpireAt=datetime.datetime(2015, 1, 1))
        print(update_resp)
        delhit_resp = mturk.delete_hit(HITId=hit['HITId'])
        print(delhit_resp)


if __name__ == "__main__":
    config = json.load(open("configs/config_instance_segmentation.json"))

    HIT = config["HIT"]
    if HIT["USE_SANDBOX"]:
        print("create HIT on sandbox")
        endpoint_url = "https://mturk-requester-sandbox.us-east-1.amazonaws.com"
        mturk_form_action = "https://workersandbox.mturk.com/mturk/externalSubmit"
        mturk_url = "https://workersandbox.mturk.com/"
    else:
        print("create HIT on mturk")
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

    input("Danger! Clearing existing qualifications and force deleting HITs! Hit enter to continue")
    clear_qualifications(mturk)
    clear_all_hits(mturk)
