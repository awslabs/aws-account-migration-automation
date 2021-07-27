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
from join_organization import get_invitation
from utils.data import get_account_data
from utils.dynamodb import get_db
from utils.sessions import get_session
from util import get_accounts_by_company_name

logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, Constant.LOG_LEVEL))

# set these data for testing
MASTER_ACCOUNT = '540351219706'
MASTER_ROLE = Constant.AWS_MASTER_ROLE
DYNAMODB_TABLE_NAME = 'MigrationEngine-AccountInfoTable-Z6MX3RB08HRW'
_SHARED_RESOURCE_BUCKET = 'Migrationengine-sharedresourcesbucket-o6wv7b0hf2ge'


def get_test_master_account(accounts) -> str:
    for account in accounts:
        if account['AccountType'] == Constant.AccountType.MASTER:
            return account['AccountId']


def restore_test_env(company_name, xlspath):
    s3_url = f"s3://{_SHARED_RESOURCE_BUCKET}/{xlspath}"
    account_data = []

    try:
        # First try to get data from Dynamodb
        try:
            account_data = get_accounts_by_company_name(table=DYNAMODB_TABLE_NAME, company_name=company_name)

        except ClientError as ce:
            logger.info(ce)
            pass
        except Exception as ex:
            logger.info(ex)
            pass

        # If no data in dynamodb then get all account in test XLS files
        if len(account_data):
            account_data = get_account_data(s3_url)

        # get master session of account form which we need ot remove all account
        master_session = get_session(f"arn:aws:iam::{MASTER_ACCOUNT}:role/{MASTER_ROLE}")
        organization_client = master_session.client('organizations')

        # get test master session of account form which we need ot add all test account
        test_master_account_id = get_test_master_account(account_data)
        if test_master_account_id:
            test_organization_client = None
            try:
                test_master_session = get_session(f"arn:aws:iam::{test_master_account_id}:role/{MASTER_ROLE}")
                test_organization_client = test_master_session.client('organizations')
                if test_organization_client.describe_organization()['Organization']['MasterAccountId'] != \
                        test_master_account_id:
                    # Make master leave org first and then create org from master account
                    organization_client.remove_account_from_organization(AccountId=test_master_account_id)
                    test_organization_client.create_organization(
                        FeatureSet='ALL'
                    )
            except ClientError as ce:
                # Note: if organization of test master account is being deleted we need ot create one
                logger.info(f"Creating organization for test master account with accountid as {test_master_account_id}")
                if test_organization_client:
                    response = test_organization_client.create_organization(
                        FeatureSet='ALL'
                    )

        for account in account_data:

            # Create session for current account
            account_session = get_session(f"arn:aws:iam::{account['AccountId']}:role/{MASTER_ROLE}")

            # Leave organization to from the master account:
            if account['Migrate'] and account['AccountType'] != Constant.AccountType.MASTER:
                try:
                    organization_client.remove_account_from_organization(AccountId=account['AccountId'])
                except Exception as ex:
                    logger.error(ex)
                    pass

            # Join organization of test account. It is not required for master or standalone accounts
            handshake_id = get_invitation(test_organization_client, account.get('AccountId'))
            try:
                if account['AccountType'] == Constant.AccountType.LINKED:
                    # Send invitation to the target account
                    if not handshake_id:
                        response = test_organization_client.invite_account_to_organization(
                            Target={'Id': account['AccountId'], 'Type': 'ACCOUNT'},
                            Notes='Invitation to join test organization Organization')
                        handshake_id = response.get('Handshake').get('Id')
                        logger.info(
                            f"Invitation with handshakeId as {handshake_id} to "
                            f"AccountId {account.get('AccountId')} sent successfully.")

                    # Send invitation to the target account
                    linked_org_client = account_session.client('organizations')
                    linked_org_client.accept_handshake(HandshakeId=handshake_id)
                    logger.info(f"Invitation {handshake_id} is being accepted by the test account successfully.")
            except Exception as ex:
                logger.error(ex)
                pass

            # Remove analyser form each region
            # TODO: remove all analyser

            # Remove all test iam role.
            iam = account_session.resource('iam')

            roles_to_deleted = set(Constant.ROLE_CONFIG.keys()).difference(set([account['AdminRole']]))
            for role in roles_to_deleted:
                try:
                    role_obj = iam.Role(role)
                    policy_arns = [policy.arn for policy in role_obj.attached_policies.all()]
                    for policy in policy_arns:
                        role_obj.detach_policy(
                            PolicyArn=policy
                        )
                    role_obj = iam.Role(role)
                    role_obj.delete()
                    logger.info(f"Role {role} is success fully deleted for account id {account['AccountId']}")
                except ClientError as ce:
                    logger.info(ce)

                # clean up dynamodb for that test company
            try:
                get_db(DYNAMODB_TABLE_NAME).delete_item(Key={
                    'CompanyName': company_name,
                    'AccountId': account['AccountId']
                })
            except ClientError as ce:
                logger.info(ce)
            logger.info(f"Successfully clean up {account['AccountId']}")

    except Exception as ex:
        logger.info(ex)


if __name__ == '__main__':
    restore_test_env("Xyz", "AWS_AE_Test.xls")
