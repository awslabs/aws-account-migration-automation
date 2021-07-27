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
  @description: Code used to get sessions in the various AWS accounts needed as part of account Migration
"""

import logging

import boto3.session

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def get_session(role_arn, session=boto3.session.Session(), session_name='AccountMigrationEngine'):
    """Assumes a role and returns a boto3.session.Session() for that role.

    if session is provided will use that session for the basis of assuming the role.
    This is useful when "hopping" through master accounts to linked accounts.

    """
    sts = session.client('sts')
    get_caller_identity = sts.get_caller_identity()
    logger.info(f"Getting session for {role_arn} as {get_caller_identity['Arn']}")

    sts = session.client('sts')
    assume_role_response = sts.assume_role(
        DurationSeconds=900,
        RoleArn=role_arn,
        RoleSessionName=session_name
    )

    role_keys = assume_role_response['Credentials']
    session = boto3.session.Session(
        aws_access_key_id=role_keys['AccessKeyId'],
        aws_secret_access_key=role_keys['SecretAccessKey'],
        aws_session_token=role_keys['SessionToken']
    )
    logger.debug(f"Got boto3 Session with AccessKeyId {role_keys['AccessKeyId']}")

    return session
