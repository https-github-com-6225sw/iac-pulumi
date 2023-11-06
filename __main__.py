"""An AWS Python Pulumi program"""

from ipaddress import ip_network
import pulumi
from pulumi_aws import s3
import pulumi_aws as aws
import json

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

# get AZ
available_az = aws.get_availability_zones(state="available").names
az_count = len(available_az)
pulumi.info(str(available_az[0]))

#get the number of subnets create
ind_range = 0
if az_count >= 3:
    ind_range = 3
else:
    ind_range = az_count
    
#get subnets block list
subnets_list = list(ip_network(vpcCidrBlock).subnets(new_prefix=24))

#create VPC
vpc = aws.ec2.Vpc(vpcName,
    cidr_block = vpcCidrBlock,
    instance_tenancy = "default",
    enable_dns_hostnames=True,
    
    tags = {
        "Name": vpcName,
    })

#internet getway
internet_gateway = aws.ec2.InternetGateway(internetGatewayName,
    vpc_id = vpc.id,
    tags={
        "Name": internetGatewayName,
    })

#public and private route table
public_route_table = aws.ec2.RouteTable(publicRouteTableName, vpc_id=vpc.id,
                                        tags={"Name": publicRouteTableName})

private_route_table = aws.ec2.RouteTable(privateRouteTableName, vpc_id=vpc.id,
                                        tags={"Name": privateRouteTableName})

#save subnets created in list
created_publicsubnets =[]
created_privatesubnets =[]
created_privatesubnetsIds= []
#create public subnets
for az_index in range(ind_range):
    public_subnet = aws.ec2.Subnet(publicSubnetsName + str(az_index),
                                  availability_zone = available_az[az_index],
                                  vpc_id=vpc.id,
                                  cidr_block = str(subnets_list[az_index]),
                                  map_public_ip_on_launch=True,
                                  tags={"Name": publicSubnetsName + str(az_index)})
    
    created_publicsubnets.append(public_subnet)
    
    public_association = aws.ec2.RouteTableAssociation(publicSubnetAssoName+str(az_index),
                                                       route_table_id=public_route_table.id,
                                                       subnet_id=public_subnet.id)
    
# #create private subnets
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

# Create a DB Subnet Group
db_subnet_group = aws.rds.SubnetGroup("my-db-subnet-group",
    subnet_ids=created_privatesubnetsIds,
    description="private DB subnet group for rds"
)
    
#add public cidr destination and gateway
public_route = aws.ec2.Route(
    "public-route",
    route_table_id=public_route_table.id,
    destination_cidr_block=destinationCidrBlock,
    gateway_id=internet_gateway.id,
)

#security group for instance
app_security_group = aws.ec2.SecurityGroup(appSecurityGroup,
    description='EC2 security group for web applications',
    vpc_id=vpc.id,
    ingress=[
        # SSH
        aws.ec2.SecurityGroupIngressArgs(
            protocol='tcp',
            from_port=22,
            to_port=22,
            cidr_blocks=['0.0.0.0/0'],
        ),
        # HTTP
        aws.ec2.SecurityGroupIngressArgs(
            protocol='tcp',
            from_port=80,
            to_port=80,
            cidr_blocks=['0.0.0.0/0'],
        ),
        # HTTPS
        aws.ec2.SecurityGroupIngressArgs(
            protocol='tcp', 
            from_port=443,
            to_port=443,
            cidr_blocks=['0.0.0.0/0'],
        ),
        # Your application port (assuming it's 8080 for this example)
        aws.ec2.SecurityGroupIngressArgs(
            protocol='tcp',
            from_port=8080,
            to_port=8080,
            cidr_blocks=['0.0.0.0/0'],
        )],
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

#security group for rds
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

user_data_content = my_rds.endpoint.apply(lambda endpoint:f"""#!/bin/bash
ENV_FILE="/etc/systemd/system/service.env"
sudo sh -c "echo 'DATABASE_URL=jdbc:mysql://{endpoint}/{databaseName}?createDatabaseIfNotExist=true' >> ${{ENV_FILE}}"
sudo sh -c "echo 'DATABASE_USER={rdsUsername}' >> ${{ENV_FILE}}"
sudo sh -c "echo 'DATABASE_PASSWORD={rdsPassword}' >> ${{ENV_FILE}}"
""")


#iam role
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

attachment = aws.iam.RolePolicyAttachment(
    "cloudWatchAgentPolicyAttachment",
    role=cloudWatch_role.name,
    policy_arn="arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy",
)

cw_profile = aws.iam.InstanceProfile("cwProfile", role= cloudWatch_role.name)

#create app instance
app_instance = aws.ec2.Instance(instanceName,
    opts=pulumi.ResourceOptions(depends_on=[my_rds]),
    ami=amiId,  # AMI ID created by workflow
    instance_type='t2.micro', 
    iam_instance_profile=cw_profile.name,
    # security_groups=[app_security_group.name], 
    vpc_security_group_ids = [app_security_group.id],
    subnet_id=created_publicsubnets[0].id,
    disable_api_termination=False,# No protection against accidental termination
    root_block_device=aws.ec2.InstanceRootBlockDeviceArgs(
        volume_size=25,
        volume_type='gp2',
        delete_on_termination=True  # ensure EBS volume is terminated with the instance
    ),
    key_name=sshkeyName,
    user_data= user_data_content,
    tags={
        'Name': instanceName,
    }
)

route53_record = aws.route53.Record(
    opts=pulumi.ResourceOptions(depends_on=[app_instance]),
    resource_name= "webServerRecord",
    zone_id= hostedZoneId,
    name= domainName,
    type= "A",
    ttl= 60,
    records= [app_instance.public_ip],
)