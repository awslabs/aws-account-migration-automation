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
import time

from constant import Constant
from utils.dynamodb import get_db

logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, Constant.LOG_LEVEL))


def get_accounts(company_name):
    """
    Fetch all record belongs to target company names.
    """
    # Custom query
    accounts = (
        get_db(Constant.DB_TABLE)
        .query(
            ProjectionExpression="CompanyName, AccountId",
            KeyConditionExpression="CompanyName = :cn",
            FilterExpression=" AccountStatus < :as",
            ExpressionAttributeValues={
                ":cn": company_name,
                ":as": Constant.AccountStatus.UPDATED,
            },
        )
        .get("Items")
    )

    for acc in accounts:
        acc[
            "ProcessName"
        ] = f"{acc['CompanyName']}-{acc['AccountId']}-{time.monotonic_ns()}"

    return accounts


def lambda_handler(event, context):
    logger.debug(f"Lambda event:{event}")
    company_name = event["CompanyName"]
    return {"CompanyName": company_name, "Accounts": get_accounts(company_name)}
