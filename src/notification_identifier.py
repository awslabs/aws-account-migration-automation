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

from constant import Constant

logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, Constant.LOG_LEVEL))


def lambda_handler(event, context):
    logger.debug(f'Lambda event:{event}')
    event["handler"] = identify_error(event)
    return event


def identify_error(error_msg: dict) -> object:
    error_code = error_msg.get("ErrorCode")

    # Error Handler mapping
    error_handlers = {
        "ConstraintViolationException": 'constraint_violation_exception_handler(error)',
        "HandshakeConstraintViolationException": "handshake_constraint_violation_exception_handler(error)",
        "DuplicateAccountException": "duplicate_account_exception_handler(error)"
    }
    return error_handlers.get(error_code, "Notify")
