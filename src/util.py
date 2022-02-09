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

import json
import logging
from time import sleep

import boto3
from botocore.exceptions import ClientError

from constant import Constant
from me_logger import log_error
from utils.dynamodb import get_db
from utils.sessions import get_session

logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, Constant.LOG_LEVEL))


# Note:
# "CompanyName" and  "AccountId" Keys in account table
# AccountType:  global Index on "CompanyName" and "AccountType"


def get_master_account(table: str = Constant.DB_TABLE, company_name: str = None):
    accounts = (
        get_db(table)
        .query(
            IndexName="AccountType",
            KeyConditionExpression="CompanyName = :cn AND AccountType = :at",
            ExpressionAttributeValues={
                ":cn": company_name,
                ":at": Constant.AccountType.MASTER,
            },
        )
        .get("Items")
    )

    if accounts and len(accounts) > 1:
        msg = f"System Error: Multiple master account found: {accounts}"
        log_error(
            logger=logger,
            account_id=None,
            company_name=company_name,
            error_type=Constant.ErrorType.AIE,
            notify=True,
            msg=msg,
        )
        raise Exception(msg)

    return accounts


def get_accounts_by_type(
    table: str = Constant.DB_TABLE, company_name: str = None, account_type: str = None
):
    return (
        get_db(table)
        .query(
            IndexName="AccountType",
            KeyConditionExpression="CompanyName = :cn AND AccountType = :at",
            ExpressionAttributeValues={":cn": company_name, ":at": account_type},
        )
        .get("Items")
    )


def get_account_by_id(
    table: str = Constant.DB_TABLE, company_name: str = None, account_id: str = None
):
    return (
        get_db(table)
        .query(
            KeyConditionExpression="CompanyName = :cn AND AccountId = :at",
            ExpressionAttributeValues={":cn": company_name, ":at": account_id},
        )
        .get("Items")
    )


def get_accounts_by_status(
    table: str = Constant.DB_TABLE, company_name: str = None, account_type: str = None
):
    return (
        get_db(table)
        .query(
            KeyConditionExpression="CompanyName = :cn ",
            FilterExpression="AccountType = :a",
            ExpressionAttributeValues={":cn": company_name, ":ma": account_type},
        )
        .get("Items")
    )


def get_account_by_status_and_id(
    table: str = Constant.DB_TABLE,
    company_name: str = None,
    account_status: str = None,
    account_id: str = None,
):
    return (
        get_db(table)
        .query(
            KeyConditionExpression="CompanyName =:cn AND AccountId =:aid ",
            FilterExpression="AccountStatus =:as",
            ExpressionAttributeValues={
                ":cn": company_name,
                ":as": account_status,
                ":aid": account_id,
            },
        )
        .get("Items")
    )


def get_accounts_by_company_name(
    table: str = Constant.DB_TABLE, company_name: str = None
):
    return (
        get_db(table)
        .query(
            KeyConditionExpression="CompanyName = :cn",
            ExpressionAttributeValues={":cn": company_name},
        )
        .get("Items")
    )


def get_all_accounts(table: str = Constant.DB_TABLE):
    return get_db(table).scan().get("Items")


def get_org_id(session=None):
    org_client = (
        session.client("organizations") if session else boto3.client("organizations")
    )
    return org_client.describe_organization()["Organization"]["Id"]


def get_parent_id(session=None, account_id=None, parent_type=None):
    org_client = (
        session.client("organizations") if session else boto3.client("organizations")
    )
    parents = org_client.list_parents(ChildId=account_id)["Parents"]
    for parent in parents:
        if parent["Type"] == parent_type:
            return parent["Id"]


def create_roles(session):
    account_id = session.client("sts").get_caller_identity()["Account"]
    logging.info(f"Creating roles for AccountId {account_id}")

    iam_client = session.client("iam")

    roles_to_create = sorted(Constant.ROLE_CONFIG.keys())
    created_roles = []
    for role in roles_to_create:
        try:
            iam_client.get_role(RoleName=role)
            logger.info(f"Role {role} already exist in AccountId {account_id}")
        except ClientError as ce:
            if ce.response["Error"]["Code"] == "NoSuchEntity":
                logger.info(f"Creating role {role} in AccountId {account_id}")
                import os

                iam_client.create_role(
                    RoleName=role,
                    AssumeRolePolicyDocument=json.dumps(
                        Constant.ROLE_CONFIG[role]["TrustPolicy"]
                    ),
                )
                role_policy = Constant.ROLE_CONFIG[role]["Policy"]
                if type(role_policy) is dict:
                    iam_client.put_role_policy(
                        RoleName=role,
                        PolicyName="RolePolicy",
                        PolicyDocument=json.dumps(role_policy),
                    )
                else:
                    iam_client.attach_role_policy(PolicyArn=role_policy, RoleName=role)
                created_roles.append(role)
                iam_client.get_waiter("role_exists").wait(RoleName=role)
                # Notes: Check MasterRole as we are going to use this role very moment after
                # creation. As role policy takes time to reflect, assume role fails. We will be assuming role to
                # make sure role and attached policies are in effect.
                if role == Constant.AWS_MASTER_ROLE:
                    while True:
                        try:
                            get_session(f"arn:aws:iam::{account_id}:role/{role}")
                            break
                        except ClientError:
                            # Note: Don't raise any Exception/Error as we are expecting client error if role is not
                            # in effect.
                            sleep(2)
                            pass
            else:
                raise ce

    return created_roles
