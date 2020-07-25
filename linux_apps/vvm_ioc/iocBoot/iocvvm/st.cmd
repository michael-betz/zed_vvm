#!../../bin/linux-x86_64/vvm

< envPaths

cd $(TOP)

## Register all support components
dbLoadDatabase("dbd/vvm.dbd", 0, 0)
vvm_registerRecordDeviceDriver(pdbbase)

## Load record instances
dbLoadRecords("db/vvm.db","P=GTL:VVM1:")

## Update IOC data
# dbl >"/vxboot/PVnames/$(IOC)"
# epicsEnvShow >"/vxboot/PVenv/$(IOC).softioc"
date

cd $(TOP)/iocBoot/iocvvm
iocInit
