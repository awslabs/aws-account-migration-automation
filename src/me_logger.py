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
from logging import Logger

from constant import Constant
from utils.notification import notify_msg


def log_error(logger: Logger = None, account_id: str = None, company_name: str = None, error_type: str = "",
              msg: str = "", error=None,
              notify: bool = False, slack_handle: str = None):
    error_code = None
    error_message = None
    try:
        if type(error).MSG_TEMPLATE:
            error_code = error.response['Error']['Code']
            error_message = error.response['Error']['Message']
    except AttributeError:
        pass

    formatted_error_msg = msg or str(error)
    logger.error(error or formatted_error_msg)

    message = {
        'Title': Constant.NOTIFICATION_TITLE,
        'AccountId': account_id,
        'CompanyName': company_name,
        'Type': error_type,
        'Message': formatted_error_msg,
        'ErrorCode': error_code,
        'ErrorMessage': error_message,
        'SlackHandle': slack_handle
    }
    if notify:
        notify_msg(Constant.NOTIFICATION_TOPIC, Constant.NOTIFICATION_TITLE, json.dumps(message))

    return formatted_error_msg
