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

import logging

import boto3

from constant import Constant
from utils.sessions import get_session

logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, Constant.LOG_LEVEL))


def get_enabled_regions(account_id=None):
    session = get_session(f"arn:aws:iam::{account_id}:role/{Constant.AWS_MASTER_ROLE}")
    if not session:
        session = boto3.session.Session()

    ec2 = session.client("ec2")
    describe_regions = ec2.describe_regions(
        Filters=[
            {
                "Name": "opt-in-status",
                "Values": ["opt-in-not-required"],
            }  # Regions that support v1 sts tokens
        ]
    )
    region_names = [region["RegionName"] for region in describe_regions["Regions"]]

    return region_names


def lambda_handler(event, context):
    logger.debug(event)

    if type(event) is list:
        event = event[0]
    event = event["Data"]

    event["Regions"] = get_enabled_regions(account_id=event["AccountId"])
    return event
