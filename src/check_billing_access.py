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

import datetime
import logging

from botocore.exceptions import ClientError

from constant import Constant
from me_logger import log_error
from util import get_account_by_id
from utils.dynamodb import update_item
from utils.sessions import get_session

logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, Constant.LOG_LEVEL))


def lambda_handler(event, context):
    logger.debug(f'Lambda event:{event}')
    account_id = event["Data"]["AccountId"]
    company_name = event["Data"]['CompanyName']
    account = {}
    try:
        account = get_account_by_id(company_name=company_name, account_id=account_id)[0]
        # Note:  Billing access check is not required for standalone account.
        if account['AccountType'] == Constant.AccountType.STANDALONE:
            event["Data"]['Status'] = Constant.StateMachineStates.COMPLETED
            return event

        session = get_session(f"arn:aws:iam::{account_id}:role/{Constant.AWS_MASTER_ROLE}")
        cost_explorer_client = session.client('ce')
        current_date = datetime.date.today()
        back_date = current_date - datetime.timedelta(days=5)
        cost_explorer_client.get_cost_and_usage(TimePeriod={
            'Start': str(back_date),
            'End': str(current_date)
        }, Granularity='DAILY', Metrics=['UnblendedCost'])
    except ClientError as ce:

        error_msg = log_error(logger=logger, account_id=account['AccountId'], company_name=account['CompanyName'],
                              error_type=Constant.ErrorType.OLPE, error=ce,
                              notify=True, slack_handle=account['SlackHandle'])
        account["Error"] = error_msg

        if ce.response.get('Error').get('Code') == 'AccessDeniedException':
            event["Data"]['Status'] = Constant.StateMachineStates.WAIT
            return event
        raise ce
    except Exception as ex:
        log_error(logger=logger, account_id=account_id, company_name=company_name,
                  error_type=Constant.ErrorType.OLPE, notify=True, error=ex)
        raise ex
    finally:
        if account:
            update_item(Constant.DB_TABLE, account)

    event["Data"]['Status'] = Constant.StateMachineStates.COMPLETED
    return event
