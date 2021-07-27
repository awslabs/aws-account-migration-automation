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

from botocore.exceptions import ClientError

from constant import Constant
from me_logger import log_error
from util import create_roles, get_master_account
from utils.dynamodb import update_item
from utils.sessions import get_session

logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, Constant.LOG_LEVEL))


def lambda_handler(event, context):
    logger.debug(f'Lambda event:{event}')
    account = None
    status = Constant.StateMachineStates.LINKED_ACCOUNT_FLOW
    account_id = None

    try:
        company_name = event['CompanyName']

        accounts = get_master_account(company_name=company_name)
        if not accounts:
            status = Constant.StateMachineStates.STANDALONE_ACCOUNT_FLOW
        else:
            account = accounts[0]
            account_id = account['AccountId']
            role_arn = f"arn:aws:iam::{account_id}:role/{account['AdminRole']}"
            account_session = get_session(role_arn)
            create_roles(account_session)

    except ClientError as ce:
        error_msg = log_error(logger=logger, account_id=account['AccountId'], company_name=account['CompanyName'],
                              error_type=Constant.ErrorType.CRME, error=ce,
                              notify=True, slack_handle=account['SlackHandle'])

        account["Error"] = error_msg
        raise ce
    except Exception as ex:
        log_error(logger=logger, account_id=event['AccountId'], company_name=account.get('CompanyName'),
                  error_type=Constant.ErrorType.CRME, notify=True, error=ex)
        raise ex
    finally:
        if account:
            update_item(Constant.DB_TABLE, account)

    return {'Data': {
        'Status': status,
        'CompanyName': company_name,
        'AccountId': account_id,
        'ProcessName': f"{company_name}-{account_id}-{time.monotonic_ns()}"}}
