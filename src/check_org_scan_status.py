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
from me_logger import log_error
from util import get_account_by_id

logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, Constant.LOG_LEVEL))


def lambda_handler(event, context):
    logger.debug(f'Lambda event:{event}')
    event["Status"] = get_account_scan_status(event)
    return event


def get_account_scan_status(event: dict) -> str:
    event = event.get("Data") or event
    try:
        account = get_account_by_id(company_name=event['CompanyName'], account_id=event['AccountId'])[0]
    except Exception as ex:
        log_error(logger=logger, account_id=event["AccountId"], company_name=event['CompanyName'],
                  error_type=Constant.ErrorType.OLPE, notify=True, error=ex)
        raise ex

    return Constant.StateMachineStates.COMPLETED if account.get("IsPermissionsScanned") \
        else Constant.StateMachineStates.WAIT
