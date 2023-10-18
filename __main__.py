"""An AWS Python Pulumi program"""

from ipaddress import ip_network
import pulumi
from pulumi_aws import s3
import pulumi_aws as aws

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
    
    ind_cidr += 1
    
    
#add public cidr destination and gateway
public_route = aws.ec2.Route(
    "public-route",
    route_table_id=public_route_table.id,
    destination_cidr_block=destinationCidrBlock,
    gateway_id=internet_gateway.id,
)

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
        ),
    ]
)

app_instance = aws.ec2.Instance(instanceName,
    ami=amiId,  # AMI ID created by workflow
    instance_type='t2.micro', 
    # security_groups=[app_security_group.name], 
    vpc_security_group_ids = [app_security_group.id],
    subnet_id=created_publicsubnets[0].id,
    disable_api_termination=False,  # No protection against accidental termination
    root_block_device=aws.ec2.InstanceRootBlockDeviceArgs(
        volume_size=25,
        volume_type='gp2',
        delete_on_termination=True  # ensure EBS volume is terminated with the instance
    ),
    key_name=sshkeyName,
    tags={
        'Name': instanceName,
    }
)