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
import ast
import logging

from botocore.exceptions import ClientError

from constant import Constant
from me_logger import log_error
from util import get_account_by_id
from utils.dynamodb import update_item

logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, Constant.LOG_LEVEL))


# noinspection PyUnusedLocal
def lambda_handler(event, context):
    """

    :param event:
    :param context:
    :return:
    """
    logger.debug(f"Lambda event:{event}")
    msg = event
    return error_handle(msg)


def error_handle(error: dict):
    """
    :Doc:  This method will check if passed error is handled one or not. if its not handled then we need to send
    slack error notification to configured slack channel.

    :param error: Type of error.
    :return: type of error handler else unhandled error notification to slack channel


    Message structure
    error = {
            "Title": "Migration Engine",
            "AccountId": "account_id",
            "CompanyName": "company_name",
            "Type": "error_type",
            "Message": "formatted_error_msg",
            "Error": "error",
            "ErrorCode": "error_code",
            "ErrorMessage": "error_message"
            "ActionItem":<Optional>
        }
        """
    error_handler = error["handler"]

    if error_handler == "Notify":
        error["Status"] = "Unhandled"
        return error
    return ast.literal_eval(error_handler)
    # return eval(error_handler)


def constraint_violation_exception_handler(error):
    """

    :param error:
    :return:
    """
    if error["ErrorMessage"].rfind("valid payment method") >= 0:
        if error.get('SlackHandle'):
            del error['SlackHandle']
        error["Status"] = "Unhandled"
        return error

    if error["ErrorMessage"].rfind("completed phone pin verification") >= 0:
        error["ActionItem"] = "Account owner need to preform required action manually. " \
                              "To complete phone pin verification someone logged in as the root user must visit this " \
                              "URL: https://portal.aws.amazon.com/gp/aws/developer/registration/index.html?client=organizations&enforcePI=True"
        error["Status"] = "Handled"

    if error["ErrorMessage"].rfind("signed the Customer Agreement") >= 0:
        error["ActionItem"] = "Account owner need to preform required action manually. " \
                              "To accept the agreement someone logged in as the root user must visit this " \
                              "URL: https://portal.aws.amazon.com/billing/signup?type=resubscribe#/resubscribed"
        error["Status"] = "Handled"

    return error


def handshake_constraint_violation_exception_handler(error):
    """

    :rtype: object
    """
    account_id = error["AccountId"]
    company_name = error["CompanyName"]
    if error.get('SlackHandle'):
        del error['SlackHandle']
    try:
        account = get_account_by_id(company_name=company_name, account_id=account_id)[0]
        account["AccountStatus"] = Constant.AccountStatus.JOINED
        update_item(Constant.DB_TABLE, account)
        error["Status"] = "Handled"
    except ClientError as ce:
        msg = f"{ce.response['Error']['Code']}: {ce.response['Error']['Message']}"
        log_error(logger=logger, account_id=account_id, company_name=company_name,
                  error_type=Constant.ErrorType.NHE, msg=msg, error=ce, notify=True)
    except Exception as ex:
        log_error(logger=logger, account_id=account_id, company_name=company_name,
                  error_type=Constant.ErrorType.NHE, notify=True, error=ex)
        raise ex
    return error


def duplicate_account_exception_handler(error):
    account_id = error["AccountId"]
    company_name = error["CompanyName"]
    error["Status"] = "Handled"
    if error.get('SlackHandle'):
        del error['SlackHandle']
    try:
        account = get_account_by_id(company_name=company_name, account_id=account_id)[0]

        account["AccountStatus"] = Constant.AccountStatus.UPDATED
        update_item(Constant.DB_TABLE, account)
    except ClientError as ce:
        msg = f"{ce.response['Error']['Code']}: {ce.response['Error']['Message']}"
        log_error(logger=logger, account_id=account_id, company_name=company_name,
                  error_type=Constant.ErrorType.NHE, msg=msg, error=ce, notify=True)
    except Exception as ex:
        log_error(logger=logger, account_id=account_id, company_name=company_name,
                  error_type=Constant.ErrorType.NHE, notify=True, error=ex)
        raise ex
    return error
