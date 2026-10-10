#!/bin/bash
qm clone 9000 201 --name k3s-01 --full
qm clone 9000 202 --name k3s-02 --full
qm clone 9000 203 --name k3s-03 --full
qm set 201 --ipconfig0 ip=192.168.77.201/24,gw=192.168.77.1 --nameserver 1.1.1.1
qm set 202 --ipconfig0 ip=192.168.77.202/24,gw=192.168.77.1 --nameserver 1.1.1.1
qm set 203 --ipconfig0 ip=192.168.77.203/24,gw=192.168.77.1 --nameserver 1.1.1.1
#  export yourpassword="123"
#  echo $yourpassword
#qm set 201 --cipassword "$yourpassword"
#qm set 202 --cipassword "$yourpassword"
#qm set 203 --cipassword "$yourpassword"
qm cloudinit update 201
qm cloudinit update 202
qm cloudinit update 203
qm reboot 201
qm reboot 202
qm reboot 203
