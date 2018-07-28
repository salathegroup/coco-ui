# MTurk hello world script - check balance of (sandbox) account
import json

import boto3

aws_key = json.load(open("keys.json"))


MTURK_SANDBOX = 'https://mturk-requester.us-east-1.amazonaws.com'
mturk = boto3.client('mturk',
                     aws_access_key_id=aws_key["aws_access_key_id"],
                     aws_secret_access_key=aws_key["aws_secret_access_key"],
                     region_name='us-east-1',
                     endpoint_url=MTURK_SANDBOX
                     )

balance = mturk.get_account_balance()['AvailableBalance']  # should be $10000 if sandbox

print("Available balance for AWS key=%s = %s" % (aws_key["aws_access_key_id"], balance))
