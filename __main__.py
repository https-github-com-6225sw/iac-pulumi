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

#create public subnets
for az_index in range(ind_range):
    public_subnet = aws.ec2.Subnet(publicSubnetsName + str(az_index),
                                  availability_zone = available_az[az_index],
                                  vpc_id=vpc.id,
                                  cidr_block = str(subnets_list[az_index]),
                                  map_public_ip_on_launch=True,
                                  tags={"Name": publicSubnetsName + str(az_index)})
    
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

