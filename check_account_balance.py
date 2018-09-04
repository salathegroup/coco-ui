# MTurk hello world script - check balance of sandbox or production account
import json

# import Amazon Python library
import boto3

# Store your AWS keys in this file
aws_key = json.load(open("keys.json"))

# Sandbox URLs are almost the same as in production - be careful!
USE_SANDBOX = False
if USE_SANDBOX:
    ENDPOINT_URL = "https://mturk-requester-sandbox.us-east-1.amazonaws.com"
else:
    ENDPOINT_URL = 'https://mturk-requester.us-east-1.amazonaws.com'

# Create a new client to interact with the Mechanical Turk API
mturk = boto3.client('mturk',
                     aws_access_key_id=aws_key["aws_access_key_id"],
                     aws_secret_access_key=aws_key["aws_secret_access_key"],
                     region_name='us-east-1',
                     endpoint_url=ENDPOINT_URL
                     )

balance = mturk.get_account_balance()['AvailableBalance']  # should be $10000 if in sandbox

print("Available balance for AWS key=%s = %s" % (aws_key["aws_access_key_id"], balance))
