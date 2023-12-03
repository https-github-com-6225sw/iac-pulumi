"""An AWS Python Pulumi program"""

from ipaddress import ip_network
import pulumi
from pulumi_aws import s3
import pulumi_aws as aws
import json
import base64
from pulumi_gcp import storage
import pulumi_gcp as gcp

aws_config = pulumi.Config("aws")
aws_region = aws_config.require("region")

gcp_config = pulumi.Config("gcp")
projectId = gcp_config.require("project")

config = pulumi.Config()
vpcCidrBlock = config.require("vpcCidrBlock")
vpcName = config.require("vpcName")
internetGatewayName = config.require("internetGatewayName")
publicRouteTableName = config.require("publicRouteTableName")
privateRouteTableName = config.require("privateRouteTableName")
publicSubnetsName = config.require("publicSubnetsName")
privateSubnetsName = config.require("privateSubnetsName")
publicSubnetAssoName = config.require("publicSubnetAssoName")
privateSubnetAssoName = config.require("privateSubnetAssoName")
destinationCidrBlock = config.require("destinationCidrBlock")
amiId = config.require("amiId")
sshkeyName = config.require("sshkeyName")
instanceName = config.require("instanceName")
appSecurityGroup = config.require("appSecurityGroup")
rdsPassword = config.require("rdsPassword")
rdsUsername = config.require("rdsUsername")
rsdIdentifier = config.require("rsdIdentifier")
databaseName = config.require("databaseName")

domainName = config.require("domainName")
hostedZoneId = config.require("hostedZoneId")
cloudWatchRoleName= config.require("cloudWatchRoleName")

topicName= config.require("topicName")
awsAccountNumber = config.require("awsAccountNumber")

### Create a new Google Service Account
service_account = gcp.serviceaccount.Account("CSYE6225sw-storage",
    account_id="csye6225sw-storage",
    display_name="CSYE6225sw-storage")

### Binding Role for service account
storage_object_user_role_binding = gcp.projects.IAMBinding("storage-object-user-role-binding",
    role="roles/storage.objectUser",
    project=projectId,
    members=[pulumi.Output.concat("serviceAccount:", service_account.email)],
)

### Create a new key for the service account
service_account_key = gcp.serviceaccount.Key("CSYE6225sw-key",
    service_account_id=service_account.name)

# get AZ
available_az = aws.get_availability_zones(state="available").names
az_count = len(available_az)
pulumi.info(str(available_az[0]))

# get the number of subnets create
ind_range = 0
if az_count >= 3:
    ind_range = 3
else:
    ind_range = az_count
    
# get subnets block list
subnets_list = list(ip_network(vpcCidrBlock).subnets(new_prefix=24))

### create VPC
vpc = aws.ec2.Vpc(vpcName,
    cidr_block = vpcCidrBlock,
    instance_tenancy = "default",
    enable_dns_hostnames=True,
    
    tags = {
        "Name": vpcName,
    })

### internet getway
internet_gateway = aws.ec2.InternetGateway(internetGatewayName,
    vpc_id = vpc.id,
    tags={
        "Name": internetGatewayName,
    })

### public and private route table
public_route_table = aws.ec2.RouteTable(publicRouteTableName, vpc_id=vpc.id,
                                        tags={"Name": publicRouteTableName})

private_route_table = aws.ec2.RouteTable(privateRouteTableName, vpc_id=vpc.id,
                                        tags={"Name": privateRouteTableName})

#save subnets created in list
created_publicsubnets =[]
created_publicsubnetsIds=[]
created_privatesubnets =[]
created_privatesubnetsIds= []

### create public subnets
for az_index in range(ind_range):
    public_subnet = aws.ec2.Subnet(publicSubnetsName + str(az_index),
                                  availability_zone = available_az[az_index],
                                  vpc_id=vpc.id,
                                  cidr_block = str(subnets_list[az_index]),
                                  map_public_ip_on_launch=True,
                                  tags={"Name": publicSubnetsName + str(az_index)})
    
    created_publicsubnets.append(public_subnet)
    created_publicsubnetsIds.append(public_subnet.id)
    public_association = aws.ec2.RouteTableAssociation(publicSubnetAssoName+str(az_index),
                                                       route_table_id=public_route_table.id,
                                                       subnet_id=public_subnet.id)
    
### create private subnets
ind_cidr = ind_range
for az_index in range(ind_range):
    private_subnet = aws.ec2.Subnet(privateSubnetsName+str(az_index),
                                    availability_zone = available_az[az_index],
                                    vpc_id=vpc.id,
                                    cidr_block=str(subnets_list[ind_cidr]),
                                    tags={"Name":privateSubnetsName+str(az_index)})
    
    private_association = aws.ec2.RouteTableAssociation(privateSubnetsName+str(az_index),
                                                       route_table_id=private_route_table.id,
                                                       subnet_id=private_subnet.id)
    
    created_privatesubnets.append(private_subnet)
    created_privatesubnetsIds.append(private_subnet.id)
    ind_cidr += 1

### Create a DB Subnet Group
db_subnet_group = aws.rds.SubnetGroup("my-db-subnet-group",
    subnet_ids=created_privatesubnetsIds,
    description="private DB subnet group for rds"
)
    
### add public cidr destination and gateway
public_route = aws.ec2.Route(
    "public-route",
    route_table_id=public_route_table.id,
    destination_cidr_block=destinationCidrBlock,
    gateway_id=internet_gateway.id,
)


### security group for load balancer
load_balancer_sg = aws.ec2.SecurityGroup('LoadBalancerSecurityGroup',
    description='Enable HTTP and HTTPS access',
    vpc_id=vpc.id,
    ingress=[
        # HTTP access from anywhere
        {'protocol': 'tcp', 'from_port': 80, 'to_port': 80, 'cidr_blocks': ['0.0.0.0/0']},
        # HTTPS access from anywhere
        {'protocol': 'tcp', 'from_port': 443, 'to_port': 443, 'cidr_blocks': ['0.0.0.0/0']},
        
    ], 
    egress=[
        # Allow all outbound traffic.
        {
            "protocol": "-1",
            "from_port": 0,
            "to_port": 0,
            "cidr_blocks": ["0.0.0.0/0"],
        }
    ],
    tags={
        "Name": "load balancer security group",
    })

### security group for instance
app_security_group = aws.ec2.SecurityGroup(appSecurityGroup,
    opts=pulumi.ResourceOptions(depends_on=[load_balancer_sg]),
    description='EC2 security group for web applications',
    vpc_id=vpc.id,
    # ingress=[
    #     # SSH
    #     aws.ec2.SecurityGroupIngressArgs(
    #         protocol='tcp',
    #         from_port=22,
    #         to_port=22,
    #         # cidr_blocks=['0.0.0.0/0'],
    #         source_security_group_id=load_balancer_sg.id,
    #     ),
    #     # HTTP
    #     aws.ec2.SecurityGroupIngressArgs(
    #         protocol='tcp',
    #         from_port=80,
    #         to_port=80,
    #         # cidr_blocks=['0.0.0.0/0'],
    #         source_security_group_id=load_balancer_sg.id,
    #     ),
        # HTTPS
        # aws.ec2.SecurityGroupIngressArgs(
        #     protocol='tcp',  
        #     from_port=443,
        #     to_port=443,
        #     # cidr_blocks=['0.0.0.0/0'],
        # ),
        # Your application port (assuming it's 8080 for this example)
        # aws.ec2.SecurityGroupIngressArgs(
        #     protocol='tcp',
        #     from_port=8080,
        #     to_port=8080,
        #     # cidr_blocks=['0.0.0.0/0'],
        #     source_security_group_id=load_balancer_sg.id,
        # )],
    egress=[aws.ec2.SecurityGroupEgressArgs(
        from_port=0,
        to_port=0,
        protocol="-1",
        cidr_blocks=["0.0.0.0/0"],
        ipv6_cidr_blocks=["::/0"],
    )],
     tags={ 
        "Name": "Security group for ec2",
    }
)


### security group for rds
database_security_group = aws.ec2.SecurityGroup("databaseSecurityGroup",
    description="My RDS security group",
    vpc_id=vpc.id,
    egress=[
        # Allow all outbound traffic.
        {
            "protocol": "-1",
            "from_port": 0,
            "to_port": 0,
            "cidr_blocks": ["0.0.0.0/0"],
        }
    ],
    tags={"Name": "DatabaseSecurityGroup"})


# Add an ingress rule for MariaDB
mysql_ingress = aws.ec2.SecurityGroupRule("mysqlIngressRule",
    type="ingress",
    from_port=3306,
    to_port=3306,
    protocol="tcp",
    security_group_id=database_security_group.id,
    source_security_group_id=app_security_group.id) 

db_parameter_group = aws.rds.ParameterGroup('csye6225-db-param-group',
                                            family='mariadb10.6',
                                            description='Custom Parameter Group for CSYE6225',)


my_rds = aws.rds.Instance("SQLInstance",
        engine="MariaDB",
        instance_class="db.t3.micro",
        allocated_storage=20,
        db_name=databaseName,
        multi_az=False,
        identifier=rsdIdentifier,
        username=rdsUsername,
        password=rdsPassword,
        # publicly_accessible=True,
        db_subnet_group_name=db_subnet_group,
        parameter_group_name=db_parameter_group.name,
        skip_final_snapshot=True,
        vpc_security_group_ids=[database_security_group.id])


def create_user_data(endpoint):
    return f"""#!/bin/bash
ENV_FILE="/etc/systemd/system/service.env"
sudo sh -c "echo 'DATABASE_URL=jdbc:mysql://{endpoint}/{databaseName}?createDatabaseIfNotExist=true' >> ${{ENV_FILE}}"
sudo sh -c "echo 'DATABASE_USER={rdsUsername}' >> ${{ENV_FILE}}"
sudo sh -c "echo 'DATABASE_PASSWORD={rdsPassword}' >> ${{ENV_FILE}}"
sudo sh -c "echo 'TOPIC_ARN=arn:aws:sns:{aws_region}:{awsAccountNumber}:{topicName}' >> ${{ENV_FILE}}"
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -s -c file:/opt/amazon-cloudwatch-config.json
"""

user_data_content = my_rds.endpoint.apply(lambda endpoint: base64.b64encode(create_user_data(endpoint).encode('utf-8')).decode('utf-8'))
# user_data_content = pulumi.Output.all(my_rds.endpoint, awsAccessKey, awsSecretKey).apply(
#     lambda args: base64.b64encode(create_user_data(args[0], args[1], args[2]).encode('utf-8')).decode('utf-8')
# )


### create iam role for cloudwatch
cloudWatch_role = aws.iam.Role(
    resource_name= cloudWatchRoleName,
    force_detach_policies= True,
    assume_role_policy=json.dumps({
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "ec2.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}),
)



#attach policy to cloudwatch role
attachment = aws.iam.RolePolicyAttachment(
    "cloudWatchAgentPolicyAttachment",
    role=cloudWatch_role.name,
    policy_arn="arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy",
)

#attachSNSAccess to template
sns_attachment = aws.iam.RolePolicyAttachment(
    "SNSAccessPolicyAttachment",
    role=cloudWatch_role.name,
    policy_arn="arn:aws:iam::aws:policy/AmazonSNSFullAccess",
    
)


# arn:aws:iam::aws:policy/AmazonSNSFullAccess
#dynamoDB
cw_profile = aws.iam.InstanceProfile("cwProfile", role= cloudWatch_role.name)

#create app instance
# app_instance = aws.ec2.Instance(instanceName,
#     opts=pulumi.ResourceOptions(depends_on=[my_rds]),
#     ami=amiId,  # AMI ID created by workflow
#     instance_type='t2.micro', 
#     iam_instance_profile=cw_profile.name,
#     # security_groups=[app_security_group.name], 
#     vpc_security_group_ids = [app_security_group.id],
#     subnet_id=created_publicsubnets[0].id,
#     disable_api_termination=False,# No protection against accidental termination
#     root_block_device=aws.ec2.InstanceRootBlockDeviceArgs(
#         volume_size=25,
#         volume_type='gp2',
#         delete_on_termination=True  # ensure EBS volume is terminated with the instance
#     ),
#     key_name=sshkeyName,
#     user_data= user_data_content,
#     tags={
#         'Name': instanceName,
#     }
# )

# Create Launch Template
launch_template = aws.ec2.LaunchTemplate('WebAppLaunchTemplate',
    opts=pulumi.ResourceOptions(depends_on=[my_rds]),
    image_id= amiId,
    name=config.require("LaunchTempName"),
    instance_type='t2.micro',
    key_name= sshkeyName,
    network_interfaces=[{
        'associate_public_ip_address': True,
        'security_groups': [app_security_group.id],
    }],
    user_data= user_data_content,
    iam_instance_profile={'name': cw_profile.name},
    tags={
        'Name': 'CSYE6625 template'
    }
)

# Create a Target Group
target_group = aws.lb.TargetGroup('appTargetGroup',
    port=8080,
    protocol='HTTP',
    target_type='instance',
    vpc_id=vpc.id,
    health_check={
        'enabled': True,
        'path': '/',  # Adjust the path according to your app's health check endpoint
        'protocol': 'HTTP',
    })


# Auto Scaling Group
auto_scaling_group = aws.autoscaling.Group('WebAppAutoScalingGroup',
    name=config.require("AutoScalingGroupName"),
    min_size=1,
    max_size=3,
    desired_capacity=1,
    default_cooldown=60,
    vpc_zone_identifiers=[created_publicsubnets[0].id],
    target_group_arns =[target_group.arn],
    launch_template={
        'id': launch_template.id,
        'version': '$Latest'
    },
    tags=[{
        'key': 'Name',
        'value': 'web-app-instance',
        'propagate_at_launch': True
    }]
)


### Auto Scaling Policies
scale_up_policy = aws.autoscaling.Policy('ScaleUp',
    autoscaling_group_name=auto_scaling_group.name,
    adjustment_type='ChangeInCapacity',
    scaling_adjustment=1,
    cooldown=60,
    policy_type='SimpleScaling')

scale_down_policy = aws.autoscaling.Policy('ScaleDown',
    autoscaling_group_name=auto_scaling_group.name,
    adjustment_type='ChangeInCapacity',
    scaling_adjustment=-1,
    cooldown=60,
    policy_type='SimpleScaling')

### CloudWatch Alarms
scale_up_alarm = aws.cloudwatch.MetricAlarm('ScaleUpAlarm',
    metric_name='CPUUtilization',
    namespace='AWS/EC2',
    statistic='Average',
    comparison_operator='GreaterThanThreshold',
    threshold=5,
    period=300,
    evaluation_periods=1,
    alarm_actions=[scale_up_policy.arn],
    dimensions={'AutoScalingGroupName': auto_scaling_group.name})

scale_down_alarm = aws.cloudwatch.MetricAlarm('ScaleDownAlarm',
    metric_name='CPUUtilization',
    namespace='AWS/EC2',
    statistic='Average',
    comparison_operator='LessThanThreshold',
    threshold=3,
    period=300,
    evaluation_periods=1,
    alarm_actions=[scale_down_policy.arn],
    dimensions={'AutoScalingGroupName': auto_scaling_group.name})

### Application Load Balancer
load_balancer = aws.lb.LoadBalancer('WebAppLoadBalancer',
    load_balancer_type='application',
    security_groups=[load_balancer_sg.id],
    subnets=created_publicsubnetsIds)

app_ingress = aws.ec2.SecurityGroupRule("appIngressRule1",
                                        type="ingress",
                                        protocol='tcp',
                                        from_port=22,
                                        to_port=22,
                                        cidr_blocks=['0.0.0.0/0'],
                                        security_group_id=app_security_group.id)
                                        # source_security_group_id=load_balancer_sg.id,)
                                        
app_ingress2 = aws.ec2.SecurityGroupRule("appIngressRule2",
                                        type="ingress",
                                        protocol='tcp',
                                        from_port=8080,
                                        to_port=8080,
                                        security_group_id=app_security_group.id,
                                        source_security_group_id=load_balancer_sg.id,)


### Create a Listener
# listener = aws.lb.Listener('httpListener',
#     load_balancer_arn=load_balancer.arn,
#     port=80,
#     default_actions=[aws.lb.ListenerDefaultActionArgs(
#         type="forward",
#         target_group_arn=target_group.arn,
#     ),])

listener = aws.lb.Listener("listener",
    load_balancer_arn=load_balancer.arn,
    port=443,
    protocol="HTTPS",
    ssl_policy="ELBSecurityPolicy-2016-08",
    certificate_arn=config.require("SSLCertificateArn"),
    default_actions=[{
        "type": "forward",
        "target_group_arn": target_group.arn
    }])


route53_record = aws.route53.Record(
    # opts=pulumi.ResourceOptions(depends_on=[app_instance]),
    resource_name= "webServerRecord",
    zone_id= hostedZoneId,
    name= domainName,
    type= "A",
    aliases=[aws.route53.RecordAliasArgs(
        name=load_balancer.dns_name,
        zone_id=load_balancer.zone_id,
        evaluate_target_health=True,
    )])


### Create IAM role for Lambda Function
lambda_role = aws.iam.Role("lambdaRole",
    assume_role_policy=json.dumps({
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "lambda.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}))

### IAM policy to be attached to the Lambda Role
# lambda_policy = aws.iam.Policy("lambdaPolicy",
#     policy=pulumi.Output.all(service_account_key.private_key).apply(lambda key: json.dumps({
#         "Version": "2012-10-17",
#         "Statement": [
#             # Add necessary permissions
#         ],
#     })))

#attach policy to lambda role
lambda_role_attachment = aws.iam.RolePolicyAttachment(
    "LambdaPolicyAttachment",
    role=lambda_role.name,
    policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
)

#attach dynamoDB Access to cloud watch
dynamoDB_attachment = aws.iam.RolePolicyAttachment(
    "dynamoDBPolicyAttachment",
    role=lambda_role.name,
    policy_arn="arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess",
    
)

def create_lambda_function(env_var):
    return aws.lambda_.Function("myLambdaFunction",
                                runtime="python3.10",
                                code=pulumi.AssetArchive({
                                    ".": pulumi.FileArchive("./my_deployment_package.zip")
                                }),
                                handler="lambda_function.lambda_handler", 
                                role=lambda_role.arn,
                                name="csye6225LambdaFunc",
                                environment={
                                    "variables": {
                                         "DYNAMO_DB_TBALE": config.require("dynamoDBName"),
                                         "SERVICE_KEY": env_var,
                                         "MAILGUN_API": config.require("mailgunAPI"),
                                         "MAILGUN_KEY": config.require_secret("mailgunKey"),
                                         "BUCKET_NAME": config.require("bucketName")
                                    }
                                })


### Create Lambda Function
lambda_function = service_account_key.private_key.apply(lambda key: create_lambda_function(key))


# lambda_function = aws.lambda_.Function("myLambdaFunction",
#                                        opts=pulumi.ResourceOptions(depends_on=[lambda_role_attachment,
#                                                                                service_account_key,]),
#     code=pulumi.FileArchive("./my_deployment_package.zip"),
#     role=lambda_role.arn,
#     handler="lambda_function.lambda_handler", 
#     runtime="python3.10",  # Specify runtime
#     environment=aws.lambda_.FunctionEnvironmentArgs(
#         variables = {
#             "SERVICE_KEY": service_account_key.private_key.apply(lambda key: key),
#             "MAILGUN_API": config.require("mailgunAPI"),
#             "MAILGUN_KEY": config.require_secret("mailgunKey")
#         },
#     ))

### Create SNS topic for post submission
submission_snstopic =aws.sns.Topic("csye6225Topic", name=topicName)

### Subscribe the Lambda function to the SNS topic 
with_sns = aws.lambda_.Permission("withSns",
    action="lambda:InvokeFunction",
    function=lambda_function.name,
    principal="sns.amazonaws.com",
    source_arn=submission_snstopic.arn)

subscription = aws.sns.TopicSubscription('mySubscription',
    topic=submission_snstopic.arn,
    protocol='lambda',
    endpoint=lambda_function.arn
)

### Create Dynamodb
dynamo_table = aws.dynamodb.Table("TrackEmail",
    attributes=[
        aws.dynamodb.TableAttributeArgs(
            name="submission_id",
            type="S",  # 'S' for string, 'N' for number, 'B' for binary
        ),
        # Add other attributes if they are part of your primary or sort keys
    ],
    name=config.require("dynamoDBName"),
    hash_key="submission_id",  # Partition key
    billing_mode="PAY_PER_REQUEST",  # or "PROVISIONED" for provisioned throughput
)