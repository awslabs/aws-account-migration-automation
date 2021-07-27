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
  @description
    Message structure
    message = {
            "Title": "Migration Engine",
            "AccountId": "account_id",
            "CompanyName": "company_name",
            "Type": "error_type",
            "Message": "formatted_error_msg",
            "Error": "error",
            "ErrorCode": "error_code",
            "ErrorMessage": "error_message"
        }
"""

import json
import logging
from datetime import datetime

from constant import Constant
from utils.notification import notify_msg

logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, Constant.LOG_LEVEL))


def lambda_handler(event, context):
    logger.info(event)
    msg = event
    if not msg.get('SlackMessage'):
        account_id = msg["AccountId"]

        title = f" {msg['Type']} \n Company: {msg['CompanyName']}"
        color = '#4caf50'

        if account_id and account_id != '':
            title = title + f"- AccountId: {account_id}"

        if event.get('Type'):
            color = '#d84315'

        if event.get('ActionItem'):
            title = f"User Action required for {title}"
            color = '#ffc107'

        text = f'```{json.dumps(event)}```' if not event.get('ActionItem') else event.get('ActionItem')

        message = dict({
            'SlackMessage': {
                'attachments': [
                    {
                        'color': color,
                        'author_name': title,
                        'author_icon': Constant.AUTHOR_ICON,
                        'title': Constant.NOTIFICATION_TITLE,
                        'text': text,
                        'footer': Constant.NOTIFICATION_NOTES,
                        'ts': datetime.now().timestamp()
                    }]
            }
        })
    else:
        message = msg
    if msg.get('SlackHandle'):
        message["WebhookUrl"] = msg.get('SlackHandle')
    notify_msg(Constant.SLACK_TOPIC, Constant.NOTIFICATION_TITLE, json.dumps(message))
