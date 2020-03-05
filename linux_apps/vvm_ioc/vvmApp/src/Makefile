TOP=../..

include $(TOP)/configure/CONFIG
#----------------------------------------
#  ADD MACRO DEFINITIONS AFTER THIS LINE
#=============================

#=============================
# Build the IOC application

PROD_IOC = vvm
# vvm.dbd will be created and installed
DBD += vvm.dbd

# vvm.dbd will be made up from these files:
vvm_DBD += base.dbd

# Include dbd files from all support applications:
#vvm_DBD += xxx.dbd

# Add all the support libraries needed by this IOC
#vvm_LIBS += xxx

# vvm_registerRecordDeviceDriver.cpp derives from vvm.dbd
vvm_SRCS += vvm_registerRecordDeviceDriver.cpp

# Build the main IOC entry point on workstation OSs.
vvm_SRCS_DEFAULT += vvmMain.cpp
vvm_SRCS_vxWorks += -nil-

# Add support from base/src/vxWorks if needed
#vvm_OBJS_vxWorks += $(EPICS_BASE_BIN)/vxComLibrary

# Finally link to the EPICS Base libraries
vvm_LIBS += $(EPICS_BASE_IOC_LIBS)

#===========================

include $(TOP)/configure/RULES
#----------------------------------------
#  ADD RULES AFTER THIS LINE

