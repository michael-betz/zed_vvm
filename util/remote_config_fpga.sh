#!/bin/bash
# Usage: config_remote.sh bitfile.bit.bin
# Used best with pre-shared ssh key and sudo without password :p
# try:
#     $ ssh-copy-id <hostname>
HOSTNAME=spaetzle.dhcp.lbl.gov
FILE_NAME=$(basename -- "$1")
scp build/csr.json $1 $HOSTNAME:
ssh $HOSTNAME "set -e; sudo cp -f $FILE_NAME /lib/firmware; echo $FILE_NAME | sudo tee /sys/class/fpga_manager/fpga0/firmware; dmesg | tail -n 1"
