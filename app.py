#!/usr/bin/env python3

import os
from aws_cdk import (
    aws_ec2 as ec2,
    aws_ssm as ssm,
    core
)

class CdkEc2BenchmarkStack(core.Stack):

    def __init__(self, scope: core.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Create subnet types private public and isolated
        subnets = []
        subnets.append(ec2.SubnetConfiguration(name = "private", subnet_type = ec2.SubnetType.PRIVATE, cidr_mask = 24))
        subnets.append(ec2.SubnetConfiguration(name = "public", subnet_type = ec2.SubnetType.PUBLIC, cidr_mask = 24))
        subnets.append(ec2.SubnetConfiguration(name = "isolated", subnet_type = ec2.SubnetType.ISOLATED, cidr_mask = 24))

        # Define VPC - Note: This will span all AZs in a region but you can manually set max_az to a numerical value for AZs to span. i.e 3 - note: also EIP usage.
        vpc = ec2.Vpc(self, "vpc", cidr="10.10.0.0/16", subnet_configuration = subnets, max_azs = len(self.availability_zones))

        # Define SG for ingress SSH (TCP:22), RDP (TCP:3389), iperf3 (TCP:5201), HTTP (TCP:80)
        pub_sg = ec2.SecurityGroup(self, "pub_sg", vpc=vpc, security_group_name = "pub_sg")
        pub_sg.add_ingress_rule(peer = ec2.Peer.ipv4("0.0.0.0/0"), connection = ec2.Port.tcp(22))
        pub_sg.add_ingress_rule(peer = ec2.Peer.ipv4("0.0.0.0/0"), connection = ec2.Port.tcp(80))
        pub_sg.add_ingress_rule(peer = ec2.Peer.ipv4("0.0.0.0/0"), connection = ec2.Port.tcp(3389))
        pub_sg.add_ingress_rule(peer = ec2.Peer.ipv4("0.0.0.0/0"), connection = ec2.Port.tcp(5001))
        pub_sg.add_ingress_rule(peer = ec2.Peer.ipv4("0.0.0.0/0"), connection = ec2.Port.tcp(5201))
        pub_sg.add_ingress_rule(peer = ec2.Peer.ipv4("0.0.0.0/0"), connection = ec2.Port.tcp(49200))
        # pub_sg.add_ingress_rule(peer = ec2.Peer.ipv4("10.10.0.0/16"), connection = ec2.Port.udp(4789))

        # Define instance type a and type b, ideally we should use same instance type.
        type_a = ec2.InstanceType(instance_type_identifier = "t3.micro")
        type_b = ec2.InstanceType(instance_type_identifier = "t3.micro")
        
        # Define UserData for Amazon Linux
        amzlinux_userdata = ec2.UserData.for_linux()
        amzlinux_userdata.add_commands("sudo yum install -y httpd")
        amzlinux_userdata.add_commands("sudo service httpd start")
        amzlinux_userdata.add_commands("sudo yum install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm")
        amzlinux_userdata.add_commands("sudo yum install -y iperf")
        amzlinux_userdata.add_commands("sudo yum install -y tcpdump")
        amzlinux_userdata.add_commands("sudo yum install -y hping3")
        amzlinux_userdata.add_commands("sudo yum install -y nc")
        amzlinux_userdata.add_commands("sudo yum install -y mtr")
        amzlinux_userdata.add_commands("sudo yum install -y jwhois")

        # Use always latest Amazon Linux AMI - Machine Image automatically updates to the latest version on every deployment.  Be aware this will cause your instances to be replaced when a new version of the image becomes available.
        amzlinux_ami = ec2.AmazonLinuxImage(user_data = amzlinux_userdata)

        # Get latest Ubuntu Linux AMI for region
        ubuntu_version = ssm.StringParameter.value_from_lookup(self, "/aws/service/canonical/ubuntu/server/20.04/stable/current/amd64/hvm/ebs-gp2/ami-id")

        # Define UserData for Ubuntu Linux
        ubuntu_userdata = ec2.UserData.for_linux()
        ubuntu_userdata.add_commands("sudo apt update && sudo apt -y install net-tools curl whois bind9-host jq ipcalc grepcidr ncat iperf3 hping3 mtr traceroute aha apache2")
        ubuntu_userdata.add_commands("sudo curl https://raw.githubusercontent.com/nitefood/asn/master/asn > /usr/bin/asn")
        ubuntu_userdata.add_commands("sudo chmod 0755 /usr/bin/asn")
        ubuntu_userdata.add_commands(
            """
            sudo echo "[Unit]
            Description=ASN lookup and traceroute server
            After=network.target
            StartLimitIntervalSec=0

            [Service]
            Type=simple
            Restart=always
            RestartSec=1
            User=ubuntu
            ExecStart=sudo asn -l 0.0.0.0 49200

            [Install]
            WantedBy=multi-user.target
            " >> /etc/systemd/system/asn.service

            """
        )
        ubuntu_userdata.add_commands("sudo setcap cap_net_raw+ep $(which mtr-packet)")
        ubuntu_userdata.add_commands("systemctl start asn")
        
        # Use always latest Ubuntu Image for region
        ubuntu_ami = ec2.GenericLinuxImage({
            stack.region: ubuntu_version
        }, user_data = ubuntu_userdata)

        # Use latest Windows Machine Image automatically updates to the latest version on every deployment. Be aware this will cause your instances to be replaced when a new version of the image becomes available.
        win_version = ec2.WindowsVersion.WINDOWS_SERVER_2019_ENGLISH_FULL_BASE
        win_ami = ec2.WindowsImage(version = win_version)

        # Define public Instance A
        instance_a = ec2.Instance(self, "pub-instance_a", instance_type = type_a, machine_image = ubuntu_ami, vpc = vpc, vpc_subnets = ec2.SubnetSelection(subnet_type = ec2.SubnetType.PUBLIC), availability_zone=stack.region + "a", security_group = pub_sg, key_name = "prod-" + stack.region + "-keypair")

        # Define public Instance B
        instance_b = ec2.Instance(self, "pub-instance_b", instance_type = type_b, machine_image = ubuntu_ami, vpc=vpc, vpc_subnets = ec2.SubnetSelection(subnet_type = ec2.SubnetType.PUBLIC), availability_zone= stack.region + "b", security_group = pub_sg, key_name = "prod-" + stack.region + "-keypair")
        
        # Define Public Instance C
        instance_c = ec2.Instance(self, "pub-instance_c", instance_type = type_b, machine_image = ubuntu_ami, vpc=vpc, vpc_subnets = ec2.SubnetSelection(subnet_type = ec2.SubnetType.PUBLIC), availability_zone= stack.region + "c", security_group = pub_sg, key_name = "prod-" + stack.region + "-keypair")

        core.CfnOutput(self, 'public-ip-instance-a', value=instance_a.instance_public_ip)
        core.CfnOutput(self, 'public-ip-instance-b', value=instance_b.instance_public_ip)
        core.CfnOutput(self, 'public-ip-instance-c', value=instance_c.instance_public_ip)
        core.CfnOutput(self, 'public-subnet-a', value=vpc.public_subnets[0].subnet_id)
        core.CfnOutput(self, 'public-subnets-b', value=vpc.public_subnets[1].subnet_id)
        core.CfnOutput(self, 'public-subnets-c', value=vpc.public_subnets[2].subnet_id)

stack = core.Environment(account=os.environ["CDK_DEPLOY_ACCOUNT"], region=os.environ["CDK_DEPLOY_REGION"])
app = core.App()
CdkEc2BenchmarkStack(app, "cdk-ec2-benchmark-" + stack.region, env=stack)

app.synth()