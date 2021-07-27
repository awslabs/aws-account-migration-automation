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
from botocore.exceptions import ClientError

from constant import Constant
from me_logger import log_error
from util import get_account_by_id, get_parent_id
from utils.dynamodb import update_item

logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, Constant.LOG_LEVEL))


def get_account_by_type_and_id():
    pass


def lambda_handler(event, context):
    logger.debug(f'Lambda event:{event}')
    event['Status'] = Constant.StateMachineStates.COMPLETED
    account = None
    try:
        account = get_account_by_id(company_name=event['CompanyName'], account_id=event['AccountId'])[0]
        # Note: We don't want to Updated OU for account that need to be suspended or already move to targeted OU.
        if account['AccountStatus'] >= Constant.AccountStatus.UPDATED:
            event['Status'] = Constant.StateMachineStates.COMPLETED
            return event

        target_account_root_id = get_parent_id(account_id=event['AccountId'], parent_type=Constant.OrgParentType.ROOT)
        if not target_account_root_id:
            msg = f"Account {event['AccountId']} of Company {event['CompanyName']} is currently at OU level we don't " \
                  f"support OU level account migration as of now."
            account['Error'] = log_error(logger=logger, account_id=account['AccountId'], company_name=account[
                'CompanyName'], error_type=Constant.ErrorType.COUE, msg=msg, notify=True,
                                         slack_handle=account['SlackHandle'])
            event['Status'] = Constant.StateMachineStates.WAIT
        _org_client = boto3.session.Session().client('organizations')
        _org_client.move_account(
            AccountId=account['AccountId'],
            SourceParentId=target_account_root_id,
            DestinationParentId=Constant.DEFAULT_OU_ID
        )
        account["AccountStatus"] = Constant.AccountStatus.UPDATED
        event['Status'] = Constant.StateMachineStates.COMPLETED

    except ClientError as ce:
        msg = f"{ce.response['Error']['Code']}: {ce.response['Error']['Message']}"
        account['Error'] = log_error(logger=logger, account_id=account['AccountId'], company_name=account[
            'CompanyName'], error_type=Constant.ErrorType.COUE, msg=msg, error=ce, notify=True,
                                     slack_handle=account['SlackHandle'])
        event['Status'] = Constant.StateMachineStates.WAIT
    except Exception as ex:
        log_error(logger=logger, account_id=event['AccountId'], company_name=event[
            'CompanyName'], error_type=Constant.ErrorType.COUE, notify=True, error=ex)
        raise ex
    finally:
        if account:
            update_item(Constant.DB_TABLE, account)

    return event
