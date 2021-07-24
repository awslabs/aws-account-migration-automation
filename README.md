# AWS-Account-Migration-Automation

Account Migration Offering automates the orchestration of the account's migration into an organization by
*	Creating a support ticket to update the billing information of an AWS account with a predefined message. 
*	Automatically scan and notify all IAM policies exposed to other AWS account or at an organization level.
*	Perform leaving the current organization, sending an invitation from target AWS account, accepting the invitation from target AWS account, and moving account to configured OU within an Organization.
*	Specific account error or failure notification without breaking the current flow.
*	Performs migration in parallel for each account.
*	Highly configurable through XLS input files.
*	Allow runtime decision-making for each account.
*	No need to log in to each account that needs to be migrated.
*	Report generation.


## Design
![Architecture](/doc/MigrationEngineDesign.png)

## Code structure
This project contains source code and supporting files for AWS Account integration automation

<pre>
.
|-- CONTRIBUTING.md
|-- LICENSE
|-- README.md
|-- doc
|   |-- MigrationEngineDesign.drawio
|   `-- MigrationEngineDesign.jpg                            [Migration Automation Design]
|-- lambda_layer
|   |-- Makefile
|   `-- requirements.txt
|-- resources
|   |-- cfn_template
|   |-- `-- MigrationEngineRole.yaml                         [Migration Role for target account]
|   |-- helper_scripts
|   |   `-- restore_test_accounts.py
|   `-- sample_xls
|       `-- test_company_accounts.xls
|-- src                                                      [Code for the application's Lambda function.]
|   |-- activate_analyzer.py
|   |-- active_regions_generator.py
|   |-- check_billing_access.py
|   |-- check_org_scan_status.py
|   |-- cleanup.py
|   |-- constant.py
|   |-- create_master_roles.py
|   |-- create_roles.py
|   |-- get_accounts.py
|   |-- get_org_dependent_resources.py
|   |-- join_organization.py
|   |-- leave_organization.py
|   |-- load_data.py
|   |-- me_logger.py
|   |-- notification_handler.py
|   |-- notification_identifier.py
|   |-- notification_observer.py
|   |-- notifier.py
|   |-- reports.py
|   |-- requirements.txt
|   |-- support_case.py
|   |-- update_account_ou.py
|   |-- update_tags.py
|   |-- util.py
|   `-- utils
|       |-- __init__.py
|       |-- data.py
|       |-- dynamodb.py
|       |-- notification.py
|       |-- parameters.py
|       `-- sessions.py
`-- template.yaml                                            [A template that defines the application's AWS resources.]

</pre>


## Notes
A account(master or standalone) that need to be migrated should have MasterRole.


```bash
$ pip install pytest pytest-mock --user
$ python -m pytest tests/ -v
```


## Build and Deployment
Application build and deployment is done using AWS SAM toolkit, make sure you have SAM toolkit installed on your machine.


#### Build 
Got to root folder of project
run 
```bash 
$ sam build
```
#### Deployment
```bash
$ sam deploy --guided
```

## License

See license [here](./LICENSE)
