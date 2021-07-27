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

from constant import Constant
from utils.sessions import get_session

logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, Constant.LOG_LEVEL))


def lambda_handler(event, context):
    """

    :rtype: object
    """
    logger.debug(f"Lambda event:{event}")
    return create_analyzer(event)


def create_analyzer(event: dict) -> dict:
    regions = event["Regions"]
    account_id = event["AccountId"]
    session = get_session(f"arn:aws:iam::{account_id}:role/{Constant.AWS_MASTER_ROLE}")

    for region in regions:
        analyzer_client = session.client("accessanalyzer", region_name=region)

        if len(analyzer_client.list_analyzers()["analyzers"]):
            analyzer = analyzer_client.create_analyzer(

                analyzerName=f"default_analyzer_{region}",
                type="ACCOUNT"
            )
            logger.debug(f"Analyzer {analyzer} created for region {region}")
        else:
            logger.debug(f"Analyzer already exist for region {region}")
    return event
