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
from util import get_master_account, get_account_by_id, create_roles
from utils.dynamodb import update_item
from utils.sessions import get_session

logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, Constant.LOG_LEVEL))


def lambda_handler(event, context):
    logger.debug(f"Lambda data:{event}")

    event = event.get("Data") or event

    company_name = event["CompanyName"]
    account_id = event["AccountId"]
    account = get_account_by_id(company_name=company_name, account_id=account_id)[0]

    try:
        role_arn = f"arn:aws:iam::{account['AccountId']}:role/{account['AdminRole']}"
        if account["AccountType"] == Constant.AccountType.LINKED:
            master_account = get_master_account(company_name=company_name)[0]
            master_role_arn = f"arn:aws:iam::{master_account['AccountId']}:role/{master_account['AdminRole']}"
            master_session = get_session(master_role_arn)
            account_session = get_session(role_arn, master_session)
        else:
            # The account is either a master or standalone account. We have direct access to the account
            # and don't need to assume role through the master.
            account_session = get_session(role_arn)

        create_roles(account_session)
        if account["AccountType"] == Constant.AccountType.STANDALONE:
            event["Status"] = Constant.StateMachineStates.STANDALONE_ACCOUNT_FLOW
        else:
            event["Status"] = Constant.StateMachineStates.COMPLETED

    except ClientError as ce:
        error_msg = log_error(
            logger=logger,
            account_id=account_id,
            company_name=company_name,
            error_type=Constant.ErrorType.CRLE,
            error=ce,
            notify=True,
            slack_handle=account["SlackHandle"],
        )

        account["Error"] = error_msg
        update_item(Constant.DB_TABLE, account)
        event["Status"] = Constant.StateMachineStates.WAIT

    except Exception as ex:
        log_error(
            logger=logger,
            account_id=account["AccountId"],
            company_name=account["CompanyName"],
            error_type=Constant.ErrorType.CRLE,
            notify=True,
            error=ex,
        )
        raise ex
    finally:
        if account:
            update_item(Constant.DB_TABLE, account)

        event["CompanyName"] = company_name
        event["AccountId"] = account_id
        event["ProcessName"] = f"{company_name}-{account_id}-{time.monotonic_ns()}"

    return {"Data": event}
