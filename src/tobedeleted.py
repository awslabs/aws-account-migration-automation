import base64
import hashlib
import hmac
import json
import logging
import os
import sys

import boto3
import pymysql
from MyHelper import MyHelper

client = boto3.client('cognito-idp')
UserPoolId = os.environ['userPoolId']

logger = logging.getLogger()
logger.setLevel(logging.INFO)

try:
    conn = pymysql.connect(os.environ['databaseURL'], user=os.environ['databaseUsername'],
                           passwd=os.environ['databaseUserpass'], db=os.environ['databaseName'], connect_timeout=10)
except:
    logger.error("ERROR: Cannot connect to database")
    sys.exit()


def checkEmailPhoneExistsSameGroup(group, tmp_email_phone):
    tmp_user_count = 0
    sql = MyHelper.querySelect(MyHelper.getTableFromGroup(group), tmp_email_phone)
    with conn.cursor(pymysql.cursors.DictCursor) as cur:
        cur.execute(sql)
        tmp_user_count = cur.rowcount
        conn.commit()
    return tmp_user_count


def checkEmailPhoneExists(tmp_email_phone):
    groups = ["Doctor", "Patient", "Operationaladmin", "Systemadmin", "Superadmin", "Hospitaladmin", "Labadmin",
              "Diagnosticadmin"]
    admins = ["Operationaladmin", "Systemadmin", "Superadmin", "Hospitaladmin", "Labadmin", "Diagnosticadmin"]
    tmp_user = {}
    for group in groups:
        sql = MyHelper.querySelect(MyHelper.getTableFromGroup(group), tmp_email_phone)
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(sql)
            for rows in cur:
                tmp_user.update({'aws_cognito_username': rows['aws_cognito_username']})
                if group in admins:
                    tmp_user.update({'user_group': rows['user_group']})
                else:
                    tmp_user.update({'user_group': group})
            conn.commit()
        if len(tmp_user) > 0:
            break
    return tmp_user


def get_secret_hash(username):
    msg = username + '3a3lva575v7qcs505aq5u9bcnu'
    dig = hmac.new(str('1m1sbuqiippjg1smai113ihvebtu9si9gm6m14nvs6fckn2rhp9k').encode('utf-8'),
                   msg=str(msg).encode('utf-8'), digestmod=hashlib.sha256).digest()
    d2 = base64.b64encode(dig).decode()
    return d2


def lambda_handler(event, context):
    try:
        Username = ''
        UserAttributes = []
        awsUsername = ''

        UserAttributes.append({'Name': 'custom:user_group', "Value": event['group']})

        if 'email' in event and event['email'] != '':
            if checkEmailPhoneExistsSameGroup(event['group'], {"email": event['email']}) == 0:
                UserAttributes.append({'Name': 'email', "Value": event['email']})
                UserAttributes.append({'Name': 'email_verified', "Value": "TRUE"})
            else:
                return {
                    'status': 'error',
                    'message': "Email already exists!",
                    'data': json.dumps("", default=MyHelper.myConverter)
                }

        mobile = None
        if 'mobile' in event and event['mobile'] != '':
            if checkEmailPhoneExistsSameGroup(event['group'], {"mobile": event['mobile']}) == 0:
                UserAttributes.append({'Name': 'phone_number', "Value": event['mobile']})
                UserAttributes.append({'Name': 'phone_number_verified', "Value": "TRUE"})
                mobile = event['mobile']
            else:
                return {
                    'status': 'error',
                    'message': "Mobile already exists!",
                    'data': json.dumps("", default=MyHelper.myConverter)
                }

        if 'username' in event and event['username'] != '':
            Username = event['username']

        # return Username

        try:
            if Username != '' and 'mobile' in event and event['mobile'] != '':
                tempPass = MyHelper.generatePassword()

                createUser = client.admin_create_user(
                    UserPoolId=UserPoolId,
                    Username=Username,
                    UserAttributes=UserAttributes,
                    # TemporaryPassword=tempPass
                    MessageAction='SUPPRESS'
                )

                Attributes = {}

                for Attribute in createUser['User']['Attributes']:
                    Attributes.update({Attribute['Name']: Attribute['Value']})

                if 'sub' in Attributes:
                    awsUsername = Attributes['sub']

                try:
                    addToGroup = client.admin_add_user_to_group(
                        UserPoolId=UserPoolId,
                        Username=Username,
                        GroupName=event['group']
                    )

                    # make the password permanent
                    client.admin_set_user_password(
                        UserPoolId=UserPoolId,
                        Username=Username,
                        Password=tempPass,
                        Permanent=True
                    )

                    # temp pass sms
                    if mobile != None:
                        text_massage = "DrKure: Thank you for joining us. It is recommended to change your temporary password immediately. Your username is " + Username + " and temporary password is " + tempPass

                        sms = boto3.client(
                            "sns",
                            aws_access_key_id=os.environ['awsAccessKey'],
                            aws_secret_access_key=os.environ['awsSecretKey'],
                            region_name="ap-south-1"
                        )

                        sms.publish(
                            PhoneNumber=mobile,
                            Message=text_massage,
                            MessageAttributes={
                                'AWS.SNS.SMS.SenderID': {
                                    'DataType': 'String',
                                    'StringValue': 'DRKUREMSG'
                                },
                                'AWS.SNS.SMS.SMSType': {
                                    'DataType': 'String',
                                    'StringValue': 'Transactional'
                                }
                            }
                        )

                    inputdata = event.copy()
                    del inputdata['group']
                    del inputdata['time_zone']
                    del inputdata['username']
                    if 'password' in inputdata:
                        del inputdata['password']
                    if 'language' in inputdata:
                        del inputdata['language']
                    if 'specialization' in inputdata:
                        del inputdata['specialization']
                    if 'degree' in inputdata:
                        del inputdata['degree']
                    if 'time' in inputdata:
                        del inputdata['time']

                    inputdata.update({'aws_cognito_username': awsUsername})
                    inputdata.update({'created': MyHelper.timeToStore('', event['time_zone'])})
                    inputdata.update({'modified': MyHelper.timeToStore('', event['time_zone'])})
                    inputdata.update({'dr_id': MyHelper.drUniqueId(event['group'])})

                    if 'lab_name' in event.keys():
                        inputdata.update({'lab_name': event['lab_name']})

                    if 'diagnostic_admin' in event.keys():
                        inputdata.update({'diagnostic_admin': event['diagnostic_admin']})

                    if 'hospital_name' in event.keys():
                        inputdata.update({'hospital_name': event['hospital_name']})

                    if 'hospital_doctor_admin' in event.keys():
                        inputdata.update({'hospital_doctor_admin': event['hospital_doctor_admin']})

                    if event['group'] == 'Patient':
                        inputdata.update({'emergency_contact': event['mobile']})

                    admins = ["Operationaladmin", "Systemadmin", "Superadmin", "Hospitaladmin", "Labadmin",
              "Diagnosticadmin"]
                    if event['group'] in admins:
                        inputdata.update({'user_group': event['group']})

                    try:
                        with conn.cursor(pymysql.cursors.DictCursor) as cur:
                            cur.execute(MyHelper.queryInsert(MyHelper.getTableFromGroup(event['group']), inputdata))
                            conn.commit()
                            if "language" in event and event['language'] != '':
                                language = event['language'].split(',')
                                for l in language:
                                    cur.execute(MyHelper.queryInsert("user_languages",
                                                                     {"aws_cognito_username": awsUsername,
                                                                      "language_id": l}))
                                    conn.commit()
                            if "specialization" in event and event['specialization'] != '' and event[
                                'group'] == 'Doctor':
                                specialization = event['specialization'].split(',')
                                for s in specialization:
                                    cur.execute(MyHelper.queryInsert("doctor_specializations",
                                                                     {"aws_cognito_username": awsUsername,
                                                                      "specialization_id": s}))
                                    conn.commit()
                            if "degree" in event and event['degree'] != '' and event['group'] == 'Doctor':
                                degree = event['degree'].split(',')
                                for d in degree:
                                    cur.execute(MyHelper.queryInsert("doctor_degrees",
                                                                     {"aws_cognito_username": awsUsername,
                                                                      "degree_id": d}))
                                    conn.commit()
                            if "time" in event and event['time'] != '' and event['group'] == 'Doctor':
                                time = event['time'].split(',')
                                for t in time:
                                    cur.execute(MyHelper.queryInsert("doctor_times",
                                                                     {"aws_cognito_username": awsUsername,
                                                                      "time_id": t}))
                                    conn.commit()

                            response = MyHelper.getSelectTable("GetUser", event['time_zone'], event['group'],
                                                               awsUsername, "")
                            return {
                                'status': 'success',
                                'message': "User created successfully. A temporary password has been sent to your registered mobile no. It is recommended to change your temporary password immediately.",
                                'data': json.dumps(response, default=MyHelper.myConverter)
                            }
                    except:
                        userdelete = client.admin_delete_user(
                            UserPoolId=UserPoolId,
                            Username=awsUsername
                        )
                        return {
                            'status': 'error',
                            'message': "An error occurred!",
                            'data': json.dumps("", default=MyHelper.myConverter)
                        }
                except:
                    return {
                        'status': 'error',
                        'message': "An error occurred!",
                        'data': json.dumps("", default=MyHelper.myConverter)
                    }
            else:
                return {
                    'status': 'error',
                    'message': "Enter phone number and username",
                    'data': json.dumps("", default=MyHelper.myConverter)
                }
        except Exception as e:
            if e.__class__.__name__ == 'UsernameExistsException':
                return {
                    'status': 'error',
                    'message': "Username already exists!",
                    'data': json.dumps("", default=MyHelper.myConverter)
                }
            else:
                return {
                    'status': 'error',
                    'message': "Invalid user input data!",
                    'data': json.dumps(e, default=MyHelper.myConverter)
                }
    except RuntimeError as e:
        return {
            'status': 'error',
            'message': "An error occurred!",
            'data': json.dumps("", default=MyHelper.myConverter)
        }
