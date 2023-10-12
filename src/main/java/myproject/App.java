package myproject;

import com.pulumi.Pulumi;
import com.pulumi.aws.AwsFunctions;
import com.pulumi.aws.Config;
import com.pulumi.aws.ec2.*;
import com.pulumi.aws.inputs.GetAvailabilityZonesArgs;
import com.pulumi.aws.outputs.GetAvailabilityZonesResult;
import com.pulumi.core.Output;
import com.pulumi.aws.s3.Bucket;
import com.pulumi.Context;
import com.pulumi.Pulumi;
import com.pulumi.core.Output;
import com.pulumi.aws.ec2.RouteTableAssociation;
import com.pulumi.aws.ec2.RouteTableAssociationArgs;
import com.pulumi.aws.ec2.SubnetArgs;
import java.util.Arrays;
import java.util.List;
import java.util.ArrayList;
import java.util.Map;
import java.io.File;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.concurrent.CompletableFuture;

import com.pulumi.aws.ec2.inputs.RouteTableRouteArgs;
import inet.ipaddr.IPAddress;

public class App {
    public static void main(String[] args) {
        Pulumi.run(App::stack);
    }

    public static void stack(Context ctx){
        //get configuration value
        var config = ctx.config();

        var awsConfig = ctx.config("aws");
        var awsRegion = awsConfig.require("region");


        final var available = AwsFunctions.getAvailabilityZones(GetAvailabilityZonesArgs.builder()
                .state("available")
                .build());
        var ids = available.applyValue(getAvailabilityZonesResult -> getAvailabilityZonesResult.zoneIds());
//        int[] count = new int[0];
//        final Output<List<String>> listOutput = ids.applyValue(values -> {
//            for (String str: values) {
//                count[0]++;
//            }
//            return null;
//        });


       int valueForPrefix = 0;
       if (awsRegion.equals("us-west-1")){
           valueForPrefix = 4 ;
       } else{
           valueForPrefix = 6;
       }

        //get subnets block array
        GetSubnets getSubnets = new GetSubnets();
        double prefix = Math.ceil(Math.sqrt(valueForPrefix));
        IPAddress[] avaliableAdress = getSubnets.adjustBlock(config.require("vpcCidrBlock"), (int) prefix);

        //create VPC
        Vpc myVpc = new Vpc(config.require("vpcName"), VpcArgs.builder()
                .cidrBlock(config.require("vpcCidrBlock"))
                .tags(Map.of("Name", config.require("vpcName")))
                .build());

        //Create Internet Gateway
        InternetGateway internetGateway = new InternetGateway(config.require("internetGatewayName"), InternetGatewayArgs.builder()
                .vpcId(myVpc.id())
                .tags(Map.of("Name",config.require("internetGatewayName")))
                .build());


        //create public route table
        RouteTable publicRouteTable = new RouteTable(config.require("publicRouteTableName"), RouteTableArgs.builder()
                .vpcId(myVpc.id())
                .tags(Map.of("Name",config.require("publicRouteTableName")))
                .build());
        //create private route table
        RouteTable privateRouteTable = new RouteTable(config.require("privateRouteTableName"), RouteTableArgs.builder()
                .vpcId(myVpc.id())
                .tags(Map.of("Name",config.require("privateRouteTableName")))
                .build());

        String publicSubnetName = config.require("publicSubnetsName");
        String privateSubnetName = config.require("privateSubnetsName");
        String publicSubnetAssoName = config.require("publicSubnetAssoName");
        String privateSubnetAssoName = config.require("privateSubnetAssoName");

        double k = 10;
        if (awsRegion.equals("us-west-1")){
             k = Math.min(k,2);
        } else{
             k = Math.min(k,3);
        }

        //create public subnets
        for (int i = 0; i < k; i++) {
            int finalI = i;
            Subnet publicSubnet = new Subnet(publicSubnetName + i, SubnetArgs.builder()
                    .vpcId(myVpc.id())
                    .cidrBlock(avaliableAdress[i].toString())
                    .tags(Map.of("Name", publicSubnetName + i))
                    .availabilityZone(available.applyValue(getAvailabilityZonesResult -> getAvailabilityZonesResult.names().get(finalI)))
                    .mapPublicIpOnLaunch(true)
                    .build());

            //add association to route table
            RouteTableAssociation publicSubnetRouteTableAssociation = new RouteTableAssociation
                    (publicSubnetAssoName + i, RouteTableAssociationArgs.builder()
                            .subnetId(publicSubnet.id())
                            .routeTableId(publicRouteTable.id())
                            .build());

        }


        //create private subnets
        int n = 0;
        for (int i = (int) k; i < k * 2; i++) {
            int finalN = n;
            Subnet privateSubnet = new Subnet(privateSubnetName + n, SubnetArgs.builder()
                    .vpcId(myVpc.id())
                    .cidrBlock(avaliableAdress[i].toString())
                    .tags(Map.of("Name", privateSubnetName + n))
                    .availabilityZone(available.applyValue(getAvailabilityZonesResult -> getAvailabilityZonesResult.names().get(finalN)))
                    .build());

            RouteTableAssociation privateSubnetRouteTableAssociation = new RouteTableAssociation
                    (privateSubnetAssoName + n, RouteTableAssociationArgs.builder()
                            .subnetId(privateSubnet.id())
                            .routeTableId(privateRouteTable.id())
                            .build());

            n++;
        }

        //add public cidr destination and gateway
        Route publicRoute = new Route(config.require("destinationCidrBlock"), RouteArgs.builder()
                .routeTableId(publicRouteTable.id())
                .destinationCidrBlock(config.require("destinationCidrBlock"))
                .gatewayId(internetGateway.id())
                .build());

        }
}
