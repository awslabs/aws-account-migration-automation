"""
  Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
  
  Licensed under the Apache License, Version 2.0 (the "License").
  You may not use this file except in compliance with the License.
  You may obtain a copy of the License at
  
      http://www.apache.org/licenses/LICENSE-2.0
 
  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.

  @author iftikhan
"""

import json
import logging
import re
from time import sleep

import boto3
from botocore.exceptions import ClientError

from constant import Constant
from util import get_account_by_id

logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, Constant.LOG_LEVEL))


def update_tags(tags_data, account):
    if tags_data:
        tags = json.loads(tags_data)
    else:
        tags = {}
    tags[account["AccountId"]] = account["Tags"]
    return tags


def get_etag(s3_client, bucket_name: str, object_key: str):
    try:
        obj = s3_client.head_object(Bucket=bucket_name, Key=object_key)
        return obj["ETag"]
    except ClientError as ce:
        if (
            ce.response["Error"]["Code"] == "AccessDenied"
            or ce.response["Error"]["Code"] == "404"
            or ce.response["Error"]["Code"] == "403"
        ):
            return ""
        raise ce


def get_data(s3_client, bucket_name: str, object_key: str):
    """Gets a Account Tags in JSON frm the provided s3 location and returns a dict of account's Tags info."""

    if not re.search(r"^\S+.json$", object_key):
        raise Exception(
            "File format not supported, Only '.json' format is supported as of now."
        )

    try:
        return s3_client.get_object(Bucket=bucket_name, Key=object_key)

    except ClientError as ce:
        if (
            ce.response["Error"]["Code"] == "AccessDenied"
            or ce.response["Error"]["Code"] == "NoSuchKey"
        ):
            return {}
        raise ce


def lambda_handler(event, context):
    logger.debug(f"Lambda event:{event}")

    account = get_account_by_id(
        company_name=event["CompanyName"], account_id=event["AccountId"]
    )[0]
    # Note: We don't want to generate tags for account that need to be suspended.
    if account["AccountStatus"] > Constant.AccountStatus.UPDATED:
        return event

    s3_client = boto3.client("s3")
    file_name = f"tag-{event['CompanyName']}.json"
    while True:
        object_tag = ""
        data = {}
        obj = get_data(s3_client, Constant.SHARED_RESOURCE_BUCKET, file_name)
        if obj.get("ETag"):
            object_tag = obj.get("ETag")
            data = obj["Body"].read()

        updated_date = update_tags(data, account)
        if object_tag == get_etag(
            s3_client, Constant.SHARED_RESOURCE_BUCKET, file_name
        ):
            s3_client.put_object(
                Body=bytes(json.dumps(updated_date), "utf-8"),
                Bucket=Constant.SHARED_RESOURCE_BUCKET,
                Key=file_name,
            )
            break
        sleep(2)

    return {
        "Status": Constant.StateMachineStates.COMPLETED,
        "CompanyName": event["CompanyName"],
    }
