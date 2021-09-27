Simple python based CDK script I use for benchmarking and general troubleshooting networking from EC2
Stack takes two environment variables ["CDK_DEPLOY_ACCOUNT"] to deploy to an AWS account along with specific region ["CDK_DEPLOY_REGION"].

Script will create VPC and subnets Public, Private and Isolated across two AZs.
With initially two EC2 instances (Latest Amazon Linux or Ubuntu 20.04 images) deployed into each Public Subnet.  Optionally Windows Image can be specified for perf testing.  Note: Tshooting tools are only installed on to Linux images.

EC2 instances have common network tshoot tools i use daily installed - iperf, tcpdump, hping3, mtr, tcpdump, netcat, asn, etc.