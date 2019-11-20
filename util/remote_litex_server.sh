#!/bin/bash
# Remotely starts up the litex server with shared memory access,
# then it tunnels the etherbone port 1234 over ssh
# needs the files from `util/litex_server` installed on zedboard
HOSTNAME=spaetzle.dhcp
ssh -L 1234:localhost:1234 $HOSTNAME "sudo litex_server --devmem --devmem-offset 0x40000000"
