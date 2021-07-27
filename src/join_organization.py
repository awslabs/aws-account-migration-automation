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
from util import get_account_by_id
from utils.dynamodb import update_item
from utils.sessions import get_session

logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, Constant.LOG_LEVEL))


def lambda_handler(event, context):
    logger.debug(f'Lambda event:{event}')
    account = None
    try:
        account = get_account_by_id(company_name=event['CompanyName'], account_id=event['AccountId'])[0]
        # Note: We don't want to join org for account that need to be suspended or already joined.
        if account['AccountStatus'] >= Constant.AccountStatus.JOINED:
            event['Status'] = Constant.StateMachineStates.COMPLETED
            return event

        _org_client = boto3.session.Session().client('organizations')
        handshake_id = get_invitation(_org_client, account.get('AccountId'))
        account['HandshakeId'] = handshake_id

        # INFO :If no invitation being sent
        if not account['HandshakeId']:
            response = _org_client.invite_account_to_organization(
                Target={'Id': account['AccountId'], 'Type': 'ACCOUNT'},
                Notes='Invitation to join AWS Organization')
            handshake_id = response.get('Handshake').get('Id')
            account['HandshakeId'] = handshake_id
            logger.info(
                f"Invitation with handshakeId as {handshake_id} to "
                f"AccountId {account.get('AccountId')} sent successfully.")

        account_session = get_session(f"arn:aws:iam::{account['AccountId']}:role/{Constant.AWS_MASTER_ROLE}")
        linked_org_client = account_session.client('organizations')
        linked_org_client.accept_handshake(HandshakeId=handshake_id)

        logger.info(
            f"Invitation with handshakeId as {handshake_id} to "
            f"AccountId {account.get('AccountId')} got accepted successfully.")
        account['AccountStatus'] = Constant.AccountStatus.JOINED
        event['Status'] = Constant.StateMachineStates.COMPLETED

    except ClientError as ce:
        # INFO: join organization API is not thread safe we need to wait in case organization is
        # busy with adding other account.
        if ce.response['Error']['Code'] == 'ConcurrentModificationException':
            event['Status'] = Constant.StateMachineStates.CONCURRENCY_WAIT
            return event

        msg = f"{ce.response['Error']['Code']}: {ce.response['Error']['Message']}"
        account['Error'] = log_error(logger=logger, account_id=account['AccountId'], company_name=account[
            'CompanyName'], error_type=Constant.ErrorType.JOE, msg=msg, error=ce, notify=True,
                                     slack_handle=account['SlackHandle'])
        event['Status'] = Constant.StateMachineStates.WAIT
    except Exception as ex:
        log_error(logger=logger, account_id=event['AccountId'], company_name=event[
            'CompanyName'], error_type=Constant.ErrorType.JOE, notify=True, error=ex)
        raise ex
    finally:
        if account:
            update_item(Constant.DB_TABLE, account)

    return event


def get_invitation(_org_client, account_id):
    handshakes = _org_client.list_handshakes_for_organization(Filter={'ActionType': 'INVITE'}).get('Handshakes')
    for handshake in handshakes:
        for party in handshake.get('Parties'):
            if handshake.get('State') == 'OPEN' and party.get('Id') == account_id and party.get('Type') == 'ACCOUNT':
                return handshake.get('Id')
