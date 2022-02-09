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

from botocore.exceptions import ClientError

from constant import Constant
from me_logger import log_error
from util import get_account_by_id, get_org_id
from utils.dynamodb import update_item
from utils.sessions import get_session

logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, Constant.LOG_LEVEL))


def get_org_level_resources(
    region: str, account: dict, session, _org_id, target_org_id
) -> dict:
    status = Constant.StateMachineStates.COMPLETED

    analyzer_client = session.client("accessanalyzer", region_name=region)

    logger.debug(f"analyzer for region: {region}")

    analysers = analyzer_client.list_analyzers()["analyzers"]

    if not analysers:
        msg = f"No Analyzer found in  region {region}"
        log_error(
            logger=logger,
            account_id=account["AccountId"],
            company_name=account["CompanyName"],
            error_type=Constant.ErrorType.OLPE,
            msg=msg,
            notify=True,
            slack_handle=account["SlackHandle"],
        )
        update_item(Constant.DB_TABLE, account)
        return Constant.StateMachineStates.WAIT

    arn = analysers[0]["arn"]
    # check for PrincipalOrgID

    org_level_resource_list = []
    org_issues = [
        resource["resource"]
        for resource in analyzer_client.list_findings(
            analyzerArn=arn,
            filter={"condition.aws:PrincipalOrgID": {"contains": [target_org_id]}},
        )["findings"]
        if resource["status"] == "ACTIVE"
    ]
    if org_issues:
        org_issues_resolved = [
            resource["resource"]
            for resource in analyzer_client.list_findings(
                analyzerArn=arn,
                filter={"condition.aws:PrincipalOrgID": {"contains": [_org_id]}},
            )["findings"]
            if resource["status"] == "ACTIVE"
        ]

        org_level_resource_list = list(
            set(org_issues).symmetric_difference(set(org_issues_resolved))
        )

    # check for PrincipalOrgID
    org_path_level_resource_list = []
    org_path_issue = [
        resource["resource"]
        for resource in analyzer_client.list_findings(
            analyzerArn=arn,
            filter={"condition.aws:PrincipalOrgPaths": {"contains": [target_org_id]}},
        )["findings"]
        if resource["status"] == "ACTIVE"
    ]
    if org_path_issue:
        org_path_resolved = [
            resource["resource"]
            for resource in analyzer_client.list_findings(
                analyzerArn=arn,
                filter={"condition.aws:PrincipalOrgPaths": {"contains": [_org_id]}},
            )["findings"]
            if resource["status"] == "ACTIVE"
        ]

        org_path_level_resource_list = list(
            set(org_path_issue).symmetric_difference(set(org_path_resolved))
        )

    org_level_permissions = org_level_resource_list + org_path_level_resource_list

    if org_level_permissions:
        status = Constant.StateMachineStates.WAIT
        for resource in org_level_permissions:
            msg = f"Resource {resource} is using organization level permission to access resource"
            log_error(
                logger=logger,
                account_id=account["AccountId"],
                company_name=account["CompanyName"],
                error_type=Constant.ErrorType.OLPE,
                msg=msg,
                notify=True,
                slack_handle=account["SlackHandle"],
            )

        account["OrgLevelPermissions"] = org_level_permissions
        update_item(Constant.DB_TABLE, account)

    return status


def lambda_handler(event, context):
    logger.debug(f"Lambda event:{event}")
    status = set({})

    account_id = event["AccountId"]
    company_name = event["CompanyName"]
    account = None

    try:
        account = get_account_by_id(company_name=company_name, account_id=account_id)[0]
        session = get_session(
            f"arn:aws:iam::{account_id}:role/{Constant.AWS_MASTER_ROLE}"
        )

        target_org_id = get_org_id(session=session)
        AWS_org_id = get_org_id()

        for region in event["Regions"]:
            status.add(
                get_org_level_resources(
                    region, account, session, AWS_org_id, target_org_id
                )
            )

        if {Constant.StateMachineStates.WAIT}.issubset(status):
            event["Status"] = Constant.StateMachineStates.WAIT
        else:
            account["IsPermissionsScanned"] = True
            event["Status"] = Constant.StateMachineStates.COMPLETED

    except ClientError as ce:
        error_msg = log_error(
            logger=logger,
            account_id=event["AccountId"],
            company_name=event["CompanyName"],
            error_type=Constant.ErrorType.OLPE,
            error=ce,
            notify=True,
            slack_handle=account.get("SlackHandle"),
        )
        account["Error"] = error_msg
        raise ce

    except Exception as ex:
        log_error(
            logger=logger,
            account_id=event["AccountId"],
            company_name=event["CompanyName"],
            error_type=Constant.ErrorType.OLPE,
            notify=True,
            error=ex,
        )
        raise ex
    finally:
        if account:
            update_item(Constant.DB_TABLE, account)

    return event
