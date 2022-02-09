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
import os

from botocore.exceptions import ClientError

from utils.parameters import get_secured_parameter

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def get_lambda_param(pram, is_ssm: bool = False, is_ssm_secured: bool = False):
    message = None
    data = os.environ.get(pram)

    if not data:
        message = f"Environment param {pram} not found"
    if is_ssm and data:
        try:
            data = get_secured_parameter(data, is_ssm_secured)
        except ClientError as ce:
            message = repr(ce)
    if message:
        logger.warning(message)
    return data


class Constant:
    # Lambda Parameters
    MASTER_ACCOUNT_ID = get_lambda_param("MASTER_ACCOUNT_ID")
    THIRD_PARTY_CLOUD_GOVERNANCE_ACCOUNT_ID = get_lambda_param(
        "THIRD_PARTY_CLOUD_GOVERNANCE_ACCOUNT_ID"
    )
    STS_EXTERNAL_ID = get_lambda_param("STS_EXTERNAL_ID")
    NOTIFICATION_TOPIC = get_lambda_param("NOTIFICATION_TOPIC")
    DB_TABLE = get_lambda_param("TARGET_ACCOUNT_TABLE_NAME")
    LOG_LEVEL = get_lambda_param("LOG_LEVEL") or "INFO"
    CASE_CC_EMAIL_ADDRESSES = (
        get_lambda_param("CASE_CC_EMAIL_ADDRESSES").split(",")
        if get_lambda_param("CASE_CC_EMAIL_ADDRESSES")
        else None
    )
    NOTIFICATION_OBSERVER_ARN = get_lambda_param("NOTIFICATION_OBSERVER_ARN")
    SHARED_RESOURCE_BUCKET = get_lambda_param("SHARED_RESOURCE_BUCKET")
    CREATE_SUPPORT_CASE = get_lambda_param("CREATE_SUPPORT_CASE")

    # Validation
    ACCOUNT_NAME_VALIDATION = get_lambda_param("ACCOUNT_NAME_VALIDATION")
    ACCOUNT_EMAIL_VALIDATION = get_lambda_param("ACCOUNT_EMAIL_VALIDATION")

    # Secure Sting SSM parameters
    SLACK_TOPIC = get_lambda_param("SLACK_TOPIC", is_ssm=True)

    # Patterns
    ACCOUNT_NAME_PATTERN = r"^([a-z]{2})(\d{7})\s{1}\w+\s{1}\w+$"
    EMAIL_PATTERN = r"^\S+@AWS.com$"

    # Lambda Status
    FAILED = 0
    SUCCESS = 1

    # STRING BOOL
    FALSE = "FALSE"
    TRUE = "TRUE"

    # Slack
    AUTHOR_NAME = "Migration Engine"
    AUTHOR_ICON = "https://i.ibb.co/R3Bs1BS/AE.png"

    # Error Type
    class ErrorType:
        AIE = "Account Integrity Error"
        CATE = "Check Account Type Error"
        CE = "Constant Error"
        COUE = "Change OU Error"
        CRLE = "Create master role in Linked account  Error"
        CRME = "Create master role in Master account error"
        CUE = "Cleanup Error"
        NHE = "Notification Handler Error"
        JOE = "Join Organization Error"
        LDE = "Load Data Error"
        LOE = "Leave Organization Error"
        OLPE = "Org Level Resource Permission Scan Error"
        RGE = "Report Generation Error"

    # SNS Email
    NOTIFICATION_NOTES = (
        "\n\n\n Note: For more info please check DynamoDB MigrationEngineTable's Error column, "
        "Step function and CloudWatch lambda logs"
    )
    NOTIFICATION_TITLE = "Migration Engine"

    DEFAULT_OU_ID = get_lambda_param("_DEFAULT_OU_ID")

    AWS_MASTER_ROLE = "MasterRole"

    class StateMachineStates:
        COMPLETED = "Completed"
        CONCURRENCY_WAIT = "ConcurrencyWait"
        LINKED_ACCOUNT_FLOW = "LinkedAccountFlow"
        STANDALONE_ACCOUNT_FLOW = "StandaloneAccountFlow"
        WAIT = "Wait"

    # Org parent typo
    class OrgParentType:
        ROOT = "ROOT"
        OU = "ORGANIZATIONAL_UNIT"

    # Role policy
    ROLE_CONFIG = {
        "MasterRole": {
            "TrustPolicy": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": MASTER_ACCOUNT_ID},
                        "Action": ["sts:AssumeRole"],
                    }
                ],
            },
            "Policy": "arn:aws:iam::aws:policy/AdministratorAccess",
        },
        "MasterReadOnlyRole": {
            "TrustPolicy": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": MASTER_ACCOUNT_ID},
                        "Action": ["sts:AssumeRole"],
                    }
                ],
            },
            "Policy": "arn:aws:iam::aws:policy/ReadOnlyAccess",
        },
    }

    class AccountStatus:
        INVITED = 1  # Account has left the current organization and ready to accept invitation.
        JOINED = 2  # Account has joined new organization.
        UPDATED = 3  # Account is moved to default OU.
        MONITORED = 4  # Account is registered .
        LEFT = 5  # Account has left the current organization and left to be closed/suspended.
        SUSPENDED = 6  # Account is closed/suspended.

    # AccountType Codes
    class AccountType:
        LINKED = "Linked"
        MASTER = "Master"
        STANDALONE = "Standalone"

    @staticmethod
    def get_support_case_subject(account_id):
        return f"Please update this payer account i.e. {account_id} and all linked accounts payment method"

    @staticmethod
    def get_support_case_desc(account_id):
        return (
            f"This company has been acquired by <CompanyName>. "
            f"This payer account i.e.{account_id} and all linked accounts will be migrated into the AWS <CompanyName>"
            f"Organization. "
            f"To facilitate this migration, we need the payment method updated for this payer "
            f"account({account_id}) and all linked accounts. "
            f"The phone number verification may be needed for each account too"
            f"This is necessary to allow linked accounts to leave this AWS Organization and join the "
            f"<CompanyName> AWS Organization. "
            f"If invoice info is presently on any of the accounts we understand you cannot update the "
            f"info so please leave as it is."
            f"\r\n \r\nPlease update this payer account({account_id}) and all linked accounts "
            f"with the below details:\r\n \r\n"
            f"PO Number: <PO Number>\r\n"
            f"Company Name: AWS Inc\r\n"
            f"Billing Contact Name: Accounts Payable\r\n"
            f"Billing address / Default payment method address:<Address>\r\n"
            f"Billing contact phone: <contact phone>\r\n"
            f"Contact email for invoice: aws-inv-notices@AWS.com\r\n \r\n"
            f"Net Term (to match new payer): 45 days\r\n \r\n"
            f"Please close this case once the payment method for the payer account({account_id}) and "
            f"all linked accounts have been updated. "
            f"This support request has been opened via automation. "
            f"This automation will check the status of the request periodically to see if this request "
            f"has been closed and will then proceed with it's next tasks.\r\n \r\n"
        )
