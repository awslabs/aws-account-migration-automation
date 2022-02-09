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

  @author: iftikhan
  @description: This file will hold logic to clean up reporting current account status.
"""

import datetime
import io
import json
import logging
import re

import boto3
import xlwt
from botocore.exceptions import ClientError
from jinja2 import Template
from xlwt.compat import basestring

from constant import Constant
from me_logger import log_error
from util import get_accounts_by_company_name, get_all_accounts
from utils.notification import notify_msg

logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, Constant.LOG_LEVEL))


def lambda_handler(event, context):
    logger.debug(f"Lambda event:{event}")
    # In case user want to run report for particular company
    company_name = event.get("CompanyName")
    # Sign URL Expire time in sec (Total 7 days)
    expires_in = 60 * 60 * 24 * 7

    try:
        if company_name:
            accounts = get_accounts_by_company_name(company_name=company_name)
            key = f"ae_report_{company_name}_{datetime.datetime.now()}"
        else:
            accounts = get_all_accounts()
            key = f"ae_report_all_accounts_{datetime.datetime.now()}"
        if not accounts:
            raise Exception("This is no account records in database to report")
        else:
            # XLS Flow
            workbook = xlwt.Workbook()
            worksheet = workbook.add_sheet("MigrationEngineReport")
            cols_data = [key for key, value in accounts[0].items()]

            # Adding headers
            for i, field_name in enumerate(cols_data):
                worksheet.write(0, i, field_name)
                worksheet.col(i).width = 6000

            style = xlwt.easyxf("align: wrap yes")
            # Adding  row data
            for row_index, row in enumerate(accounts):
                for cell_index, cell_value in enumerate(row.items()):
                    cell_value = cell_value[1]
                    if isinstance(cell_value, basestring):
                        cell_value = re.sub("\r", " ", cell_value)
                    if not cell_value:
                        cell_value = None
                    worksheet.write(row_index + 1, cell_index, cell_value, style)

            # uncomment below line if you want to save it in local file system
            # workbook.save('output.xls')

            # Reading xls data to upload on s3
            try:
                fp = io.BytesIO()
                workbook.save(fp)
                fp.seek(0)
                data = fp.read()
            except IOError as ioe:
                logger.error(ioe)
            finally:
                fp.close()

            # Uploading xls data to upload to s3
            s3_client = boto3.client("s3")
            s3_client.put_object(
                Body=data, Bucket=Constant.SHARED_RESOURCE_BUCKET, Key=f"{key}.xls"
            )

            # generate pre-signed url
            xls_link = s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": Constant.SHARED_RESOURCE_BUCKET, "Key": f"{key}.xls"},
                ExpiresIn=expires_in,
            )

            # HTML Flow
            # jinja2 Template
            template = Template(
                "<table> "
                "{% set glob={'isHeader':true} %}"
                "{% for account in accounts %}"
                "{% if glob.isHeader %}"
                "{% set _ = glob.update({'isHeader':false}) %}"
                "<tr  style='background: gray;'>"
                "{% for key,value in account.items() %}"
                "<th > {{ key }} </th>"
                "{% endfor %}"
                "</tr>"
                "{% endif %}"
                "<tr>"
                "{% for key,value in account.items() %}"
                "<td> {{ value }} </td>"
                "{% endfor %}"
                "</tr>"
                "{% endfor %}"
                "</table>"
                "<style>"
                "th {background-color: #4CAF50;color: white;}"
                "th, td {padding: 5px;text-align: left;}"
                "tr:nth-child(even) {background-color: #f2f2f2;}"
                "</style>"
            )

            # Generate HTML
            report_data = template.render(accounts=accounts)
            # Upload HTML data to s3
            s3_client.put_object(
                Body=bytes(report_data, "utf-8"),
                Bucket=Constant.SHARED_RESOURCE_BUCKET,
                Key=f"{key}.html",
            )
            # generate pre-signed url
            html_link = s3_client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": Constant.SHARED_RESOURCE_BUCKET,
                    "Key": f"{key}.html",
                },
                ExpiresIn=expires_in,
            )

            notify_data = {
                "SlackHandle": None,
                "SlackMessage": {
                    "attachments": [
                        {
                            "color": "#0ec1eb",
                            "author_name": Constant.AUTHOR_NAME,
                            "author_icon": Constant.AUTHOR_ICON,
                            "title": "Migration Engine Reports",
                            "text": f"Click <{xls_link}|Report.xls> for XLS report.\n"
                            f"Click <{html_link}|Report.html> for HTML report.\n"
                            f"Above reports links will expire after 7 days.",
                            "footer": Constant.NOTIFICATION_NOTES,
                            "ts": datetime.datetime.now().timestamp(),
                        }
                    ]
                },
            }
            notify_msg(
                Constant.NOTIFICATION_TOPIC,
                Constant.NOTIFICATION_TITLE,
                json.dumps(notify_data),
            )

    except ClientError as ce:
        log_error(
            logger=logger,
            account_id=None,
            company_name=company_name or "All Companies",
            error=ce,
            error_type=Constant.ErrorType.RGE,
            notify=True,
        )
        raise ce
    except Exception as ex:
        log_error(
            logger=logger,
            account_id=None,
            company_name=company_name or "All Companies",
            error_type=Constant.ErrorType.RGE,
            notify=True,
            error=ex,
        )
        raise ex

    return {
        "Status": Constant.StateMachineStates.COMPLETED,
        "CompanyName": company_name,
    }


lambda_handler({}, None)
