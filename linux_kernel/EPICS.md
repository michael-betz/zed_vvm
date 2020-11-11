# Compiling EPICS
These steps could be ran directly on the Zynq. However space on the SD card and CPU power is very limited. So here's how to do it on the host machine with qemu instead. The compiled binaries (IOCs) can then be copied to the Zynq machine and executed there, without having to install the whole development environment.

## On the host machine
```bash
# Download and unpack the minimal rootfs image
wget https://github.com/yetifrisstlama/zed_vvm/releases/download/v0.1/rootfs_buster_clean.tar.gz
mkdir rootfs
cd rootfs
sudo tar -xzvf ../rootfs_buster_clean.tar.gz
cd ..

# Copy the qemu binary for arm emulation
sudo apt install qemu qemu-user-static binfmt-support
sudo cp /usr/bin/qemu-arm-static rootfs/usr/bin/

# enter the `virtual machine`
sudo chroot rootfs/
```

## On the zedboard / in chroot
```bash
su zed

# Install development tools
sudo apt update
sudo apt upgrade
sudo apt install clang libreadline-dev build-essential git

# Download epics source
mkdir EPICS_R3_16
cd EPICS_R3_16
git clone --recursive --branch 3.16 https://github.com/epics-base/epics-base.git
cd epics-base

# Compile epics
export HOST_ARCH=linux-arm
export EPICS_HOST_ARCH=linux-arm
make -j4
make runtests
# epicsCalcTest.t          (Wstat: 0 Tests: 613 Failed: 38)
# Failed tests:  225, 511, 522, 578-604, 606-61
export EPICS_BASE=/home/zed/EPICS_R3_16/epics-base
export PATH=${EPICS_BASE}/bin/linux-arm:${PATH}

# Collect the needed libraries and binaries in one directory
mkdir ~/zed_epics
cd ~/zed_epics/
cp -r $EPICS_BASE/bin .
cp -r $EPICS_BASE/lib .
exit

# from the host: copy it to zedboard
scp -r rootfs/home/zed/zed_epics zed@zedboard:~

# on the zedboard, add them to the environment (.bashrc maybe)
ssh zed@zedboard
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$HOME/zed_epics/lib/linux-arm
export PATH=$PATH:$HOME/zed_epics/bin/linux-arm

# test it!!
cainfo -V
    EPICS Version EPICS 3.16.2-DEV, CA Protocol version 4.13
```

## Compile a dummy soft-IOC
```
# back in the chroot VM:
mkdir ~/test_ioc
cd ~/test_ioc
makeBaseApp.pl -t example test
makeBaseApp.pl -t example -i -p test test
make
exit

# back on the host-machine, copy the IOC files to the actual zedboard
scp -r rootfs/home/zed/test_ioc zed@zedboard:~

# on the zedboard: run it!
ssh zed@zedboard
cd ~/test_ioc/iocBoot/ioctest
./st.cmd
    ...
    ###########################################################################
    ## EPICS R3.16.2-DEV
    ## EPICS Base built Nov 11 2020
    ############################################################################
    iocRun: All initialization complete
    ## Start any sequence programs
    #seq sncExample, "user=zed"
    epics> dbl
    zed:subExample
    zed:compressExample
    ...
    epics>
```


