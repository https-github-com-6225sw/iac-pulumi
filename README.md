# iac-pulumi



## Description

Setting up networking resources such as Virtual Private Cloud (VPC), Internet Gateway, Route Table, and Routes by Pulumi.

## Getting Started

### Dependencies

* Python3
* mac
* Pulumi
  

### Executing program

* install pulumi
```
brew install pulumi/tap/pulumi
```
* run
```
pulumi up
```
### Import SSL Certificate to AWS by CLI

* Put certificate-chain.pem, my-server-vertificate.pem, and my-private-key.pem in the same folder

* cd the this folder

* Run
```
aws iam upload-server-certificate --server-certificate-name certificate_object_name --certificate-body file://my-server-certificate.pem --    private-key file://my-private-key.pem --certificate-chain file://certificate-chain.pem
```
  

  
