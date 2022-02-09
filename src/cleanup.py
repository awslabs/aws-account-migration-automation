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
  @description: This file will hold logic to clean up pending account.
    ->  Case:- if there are any account which need to be close then keep on checking the status and send notification to
    account owner every week or so

    -> If everything look ok then this will terminate step function
    """

import json
import logging
from datetime import datetime

from botocore.exceptions import ClientError

from constant import Constant
from me_logger import log_error
from utils.dynamodb import get_db, update_item
from utils.notification import notify_msg
from utils.sessions import get_session

logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, Constant.LOG_LEVEL))


def lambda_handler(event, context):
    logger.debug(f"Lambda event:{event}")
    company_name = event["CompanyName"]
    status = Constant.StateMachineStates.WAIT

    # check left over accounts to send Notification
    left_accounts = (
        get_db(Constant.DB_TABLE)
        .query(
            IndexName="AccountType",
            KeyConditionExpression="CompanyName = :cn ",
            FilterExpression="AccountStatus = :asi",
            ExpressionAttributeValues={
                ":cn": company_name,
                ":asi": Constant.AccountStatus.LEFT,
            },
        )
        .get("Items")
    )

    if left_accounts:
        for account in left_accounts:

            try:
                # Note: if assume MasterRole role fails, consider account as closed.
                get_session(
                    f"arn:aws:iam::{account['AccountId']}:role/{Constant.AWS_MASTER_ROLE}"
                )

                notify_data = {
                    "SlackHandle": account["SlackHandle"],
                    "SlackMessage": {
                        "attachments": [
                            {
                                "color": "#0ec1eb",
                                "author_name": Constant.AUTHOR_NAME,
                                "author_icon": Constant.AUTHOR_ICON,
                                "title": "User Action Required",
                                "text": f"Account: {account['AccountId']}  of company {company_name} "
                                f"is being removed from the current organization. Please close the "
                                f"account using your root username/password.",
                                "footer": "Note: This is an automated notification.",
                                "ts": datetime.now().timestamp(),
                            }
                        ]
                    },
                }

                notify_msg(
                    Constant.NOTIFICATION_TOPIC,
                    Constant.NOTIFICATION_TITLE,
                    json.dumps(notify_data),
                )

            except ClientError as ce:
                if ce.response["Error"]["Code"] == "AccessDenied":
                    account["AccountStatus"] = Constant.AccountStatus.SUSPENDED
                    update_item(Constant.DB_TABLE, account)

                account["Error"] = log_error(
                    logger=logger,
                    account_id=account["AccountId"],
                    company_name=account["CompanyName"],
                    error=ce,
                    error_type=Constant.ErrorType.LOE,
                    notify=True,
                    slack_handle=account["SlackHandle"],
                )
            except Exception as ex:
                log_error(
                    logger=logger,
                    account_id=event["AccountId"],
                    company_name=event["CompanyName"],
                    error_type=Constant.ErrorType.LOE,
                    notify=True,
                    error=ex,
                )
                raise ex
    else:
        # check if all account get processed.
        in_process_accounts = (
            get_db(Constant.DB_TABLE)
            .query(
                IndexName="AccountType",
                KeyConditionExpression="CompanyName = :cn ",
                FilterExpression="AccountStatus < :asi AND Migrate = :mi",
                ExpressionAttributeValues={
                    ":cn": company_name,
                    ":asi": Constant.AccountStatus.UPDATED,
                    ":mi": True,
                },
            )
            .get("Items")
        )

        if not in_process_accounts and not left_accounts:
            notify_data = {
                "SlackHandle": None,
                "SlackMessage": {
                    "attachments": [
                        {
                            "color": "#0ec1eb",
                            "author_name": Constant.AUTHOR_NAME,
                            "author_icon": Constant.AUTHOR_ICON,
                            "title": "Migration Engine Stopped",
                            "text": f"Migration Engine ran successfully for company {company_name}",
                            "footer": Constant.NOTIFICATION_NOTES,
                            "ts": datetime.now().timestamp(),
                        }
                    ]
                },
            }
            notify_msg(
                Constant.NOTIFICATION_TOPIC,
                Constant.NOTIFICATION_TITLE,
                json.dumps(notify_data),
            )
            status = Constant.StateMachineStates.COMPLETED

    return {"Status": status, "CompanyName": company_name}


if __name__ == "__main__":
    lambda_handler({"CompanyName": "Xyz"}, None)
