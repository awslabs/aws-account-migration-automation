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
import re

from botocore.exceptions import ClientError

from constant import Constant
from me_logger import log_error
from util import get_account_by_id, get_master_account
from utils.dynamodb import update_item
from utils.sessions import get_session

logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, Constant.LOG_LEVEL))


def leave_org(event):
    account = None
    try:
        event['Status'] = Constant.StateMachineStates.COMPLETED
        account = get_account_by_id(company_name=event['CompanyName'], account_id=event['AccountId'])[0]

        # INFO: If account already left the organization
        if account['AccountStatus'] >= Constant.AccountStatus.INVITED:
            event['Status'] = Constant.StateMachineStates.COMPLETED
            return event

        # INFO: Linked Account flow
        if account["AccountType"] == Constant.AccountType.LINKED:
            # INFO: Get target master account but don't send invitation to master until all linked accounts joins
            # the AWS master account
            master_record = get_master_account(company_name=event['CompanyName'])[0]

            master_account_id = master_record['AccountId']
            master_session = get_session(f"arn:aws:iam::{master_account_id}:role/{master_record['AdminRole']}")
            organization_client = master_session.client('organizations')

            account_info = organization_client.describe_account(AccountId=account['AccountId'])

            arn = account_info['Account']['Arn']
            account['Email'] = account_info['Account']['Email']
            account['Name'] = account_info['Account']['Name']

            # INFO: Double check in case user already accepted the invitation.
            if arn.find(f'arn:aws:organizations::{Constant.MASTER_ACCOUNT_ID}') > 0:
                account['AccountStatus'] = Constant.AccountStatus.JOINED
                event['Status'] = 'JoinCH'
                return event

            # INFO: Check if account have already updated its account info as per AWS standards and
            # ready to accept invitation from AWS organization.
            if Constant.ACCOUNT_EMAIL_VALIDATION.__eq__(Constant.TRUE) and not bool(
                    re.search(Constant.EMAIL_PATTERN, account['Email'])):
                msg = f"AccountId({account['AccountId']}): Email is not AWS's org compatible"
                account['Error'] = log_error(logger=logger, account_id=account['AccountId'], company_name=account[
                    'CompanyName'], error_type=Constant.ErrorType.CATE, msg=msg, notify=True,
                                             slack_handle=account['SlackHandle'])
                event['Status'] = Constant.StateMachineStates.WAIT
                return event

            if Constant.ACCOUNT_NAME_VALIDATION.__eq__(Constant.TRUE) and not bool(
                    re.search(Constant.ACCOUNT_NAME_PATTERN, account['Name'])):
                msg = f"AccountId({account['AccountId']}): Account name is not AWS's org compatible"
                account['Error'] = log_error(logger=logger, account_id=account['AccountId'], company_name=account[
                    'CompanyName'], error_type=Constant.ErrorType.CATE, msg=msg, notify=True,
                                             slack_handle=account['SlackHandle'])
                event['Status'] = Constant.StateMachineStates.WAIT

            organization_client.remove_account_from_organization(AccountId=account['AccountId'])

        # Master account Flow
        elif account["AccountType"] == Constant.AccountType.MASTER:
            master_session = get_session(f"arn:aws:iam::{account['AccountId']}:role/{account['AdminRole']}")
            organization_client = master_session.client('organizations')

            if len(organization_client.list_accounts()["Accounts"]) > 1:
                event['Status'] = Constant.StateMachineStates.WAIT
                return event
            else:
                organization_client.delete_organization()

        # Standalone account Flow
        elif account["AccountType"] == Constant.AccountType.STANDALONE:
            session = get_session(f"arn:aws:iam::{account['AccountId']}:role/{Constant.AWS_MASTER_ROLE}")
            # Note: Double check for standalone account, if account have any organization associated with it.
            try:
                organization_client = session.client('organizations')
                organization_client.list_accounts()["Accounts"]
                raise Exception(f"Standalone account {account['AccountId']} has organization setup.")
            except ClientError as ce:
                # below exception occur if there is no organization attached to account.
                if ce.response['Error']['Code'] == 'AWSOrganizationsNotInUseException':
                    pass

        account['AccountStatus'] = Constant.AccountStatus.INVITED if account['Migrate'] \
            else Constant.AccountStatus.LEFT
        event['Status'] = Constant.StateMachineStates.COMPLETED

        return event

    except ClientError as ce:
        # INFO: Below exception will occur when The member account have no organization or already left the
        # organization
        if ce.response['Error']['Code'] == 'AccountNotFoundException':
            account['AccountStatus'] = Constant.AccountStatus.INVITED
            event['Status'] = Constant.StateMachineStates.COMPLETED
            return event

        account['Error'] = log_error(logger=logger, account_id=account['AccountId'], company_name=account[
            'CompanyName'], error=ce, error_type=Constant.ErrorType.LOE, notify=True,
                                     slack_handle=account['SlackHandle'])

        event['Status'] = Constant.StateMachineStates.WAIT

    except Exception as ex:
        log_error(logger=logger, account_id=event['AccountId'], company_name=event[
            'CompanyName'], error_type=Constant.ErrorType.LOE, notify=True, error=ex)
        raise ex

    finally:
        if account:
            update_item(Constant.DB_TABLE, account)

    return event


def lambda_handler(event, context):
    logger.debug(f'Lambda event:{event}')
    return leave_org(event.get("Data") or event)
