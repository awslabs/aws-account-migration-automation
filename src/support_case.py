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
from util import get_master_account
from utils.dynamodb import update_item

logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, Constant.LOG_LEVEL))


def lambda_handler(event, context):
    logger.debug(f"Lambda event:{event}")

    event = event.get("Data") or event
    account = None
    status = Constant.StateMachineStates.WAIT
    company_name = event["CompanyName"]
    support = boto3.client("support")

    try:
        if Constant.CREATE_SUPPORT_CASE == Constant.TRUE:
            account = get_master_account(company_name=company_name)[0]

            if account.get("SupportCaseId"):
                if (
                    support.describe_cases(caseIdList=[account.get("SupportCaseId")])
                    .get("cases")[0]
                    .get("status")
                    .lower()
                    == "resolved"
                ):
                    account["SupportCaseStatus"] = "resolved"
                    status = Constant.StateMachineStates.COMPLETED
                else:
                    status = Constant.StateMachineStates.WAIT
            else:
                account_id = account.get("AccountId")
                response = support.create_case(
                    subject=Constant.get_support_case_subject(account_id),
                    severityCode="normal",
                    categoryCode="update-billing-details",
                    serviceCode="billing",
                    language="en",
                    issueType="customer-service",
                    ccEmailAddresses=Constant.CASE_CC_EMAIL_ADDRESSES,
                    communicationBody=Constant.get_support_case_desc(account_id),
                )

                case_id = response["caseId"]
                case = support.describe_cases(caseIdList=[case_id])
                case_display_id = case["cases"][0].get("displayId")
                case_status = case.get("cases")[0].get("status")
                account["SupportCaseId"] = case_id
                account["SupportCaseDisplayId"] = case_display_id
                account["SupportCaseStatus"] = case_status

                status = Constant.StateMachineStates.WAIT
        else:
            status = Constant.StateMachineStates.COMPLETED

    except ClientError as ce:
        msg = f"{ce.response['Error']['Code']}: {ce.response['Error']['Message']}"
        account["Error"] = log_error(
            logger=logger,
            account_id=account["AccountId"],
            company_name=account["CompanyName"],
            error_type=Constant.ErrorType.LOE,
            error=ce,
            msg=msg,
            notify=True,
            slack_handle=account["SlackHandle"],
        )
    except Exception as ex:
        log_error(
            logger=logger,
            account_id=None,
            company_name=event["CompanyName"],
            error_type=Constant.ErrorType.LOE,
            notify=True,
            error=ex,
        )
        raise ex
    finally:
        if account:
            update_item(Constant.DB_TABLE, account)

    return {"Status": status, "CompanyName": company_name}
