import boto3
import json
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


def get_results_for_hit(hit_id):
    """Return a list of all worker responses for this HIT"""
    worker_results = mturk.list_assignments_for_hit(HITId=hit_id)

    responses = []

    for assignment in worker_results['Assignments']:
        response = mturk.get_assignment(
            AssignmentId=assignment['AssignmentId']
        )
        xml_doc = xmltodict.parse(response['Assignment']['Answer'])
        answer = json.loads(xml_doc['QuestionFormAnswers']['Answer']['FreeText'])
        print(answer)

        responses.append(response)

    return responses


def get_all_hits():
    """Get results for all HITs from requester. Returns dict mapping each hit_id to its responses"""
    resp = mturk.list_hits()
    hit_ids = [hit["HITId"] for hit in resp["HITs"]]

    results = dict()

    for hit_id in hit_ids:
        results[hit_id] = get_results_for_hit(hit_id)
        print(hit_id, get_results_for_hit(hit_id))

    return results


if __name__ == "__main__":
    get_all_hits()
