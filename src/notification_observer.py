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
  @description
    Message structure
    message = {
            'Title': 'Migration Engine',
            'AccountId': account_id,
            'CompanyName': company_name,
            'Type': error_type,
            'Message': formatted_error_msg,
            'Error': error,
            'ErrorCode': error_code,
            'ErrorMessage': error_message
        }

"""

import json
import logging
import time

import boto3

from constant import Constant

logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, Constant.LOG_LEVEL))


def lambda_handler(event, context):
    logger.debug(f"Lambda event:{event}")
    msg = event["Records"][0]["Sns"]["Message"]
    return handle_error(json.loads(msg))


def handle_error(error: dict):
    sfn_client = boto3.client("stepfunctions")
    sfn_client.start_execution(
        stateMachineArn=Constant.NOTIFICATION_OBSERVER_ARN,
        name=f"{error.get('CompanyName') or 'General'}-"
        f"{error.get('AccountId') or 'Notification'}-"
        f"{error.get('ErrorCode') or ''}-{time.monotonic_ns()}",
        input=json.dumps(error),
    )
