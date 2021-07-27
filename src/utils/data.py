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
  @description: Code used to get or write data
"""

import logging
import re

import boto3
from xlrd.book import open_workbook_xls

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def get_account_data(s3_url: str):
    """Gets a XLS from the provided s3_url and returns a dict of account info. """

    if 's3://' not in s3_url:
        raise ValueError(f's3_url was set to {s3_url} and did not include s3://')

    s3_path = s3_url.split('/', 3)  # Max split of 3 means object key will be a single item even if it has "/"
    bucket_name = s3_path[2]
    object_key = s3_path[3]

    if not (bool(bucket_name) and bool(object_key)):
        raise ValueError(f'bucket_name or object_key is either None or Empty')

    if not re.search(r'^\S+.xls$', object_key):
        raise Exception("File format not supported, Only '.xsl' format is supported as of now.")

    xls = get_s3_data(bucket_name, object_key)
    account_data = process_xls(xls)
    return account_data


def get_s3_data(bucket_name, object_key):
    logger.info(f'Getting s3://{bucket_name}/{object_key}')
    s3 = boto3.client('s3')
    get_object = s3.get_object(Bucket=bucket_name, Key=object_key)
    file_content = get_object['Body'].read()
    return file_content


def process_xls(xls: bytes):
    workbook = open_workbook_xls(file_contents=xls)
    worksheet = workbook.sheet_by_index(0)
    first_row = [worksheet.cell_value(0, col) for col in range(worksheet.ncols)]

    account_info_list = []
    for row in range(1, worksheet.nrows):
        account_info = dict({})
        for col in range(worksheet.ncols):
            key = first_row[col]
            value = worksheet.cell_value(row, col)
            if type(value) is float:
                value = str(int(value))
            elif type(value) is not str:
                value = str(value)

            if key == 'AccountId':
                value = value.zfill(12)

            if key == 'Migrate':
                if value.lower() in ['true', '1']:
                    value = True
                else:
                    value = False

            account_info[key] = value
        account_info_list.append(account_info)

    return account_info_list
