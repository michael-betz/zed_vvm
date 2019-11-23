include ../../bedrock/dir_list.mk
include $(BUILD_DIR)/top_rules.mk
include $(CORDIC_DIR)/rules.mk

vpath %.v $(CORDIC_DIR) $(DSP_DIR)

# TARGET  = reg_delay
TARGET  = vvm_dsp

SRC_V  += cordicg_b22.v cstageg.v addsubg.v
SRC_V  += mixer.v
SRC_V  += multi_sampler.v cic_multichannel.v
SRC_V  += serializer_multichannel.v reg_delay.v ccfilt.v double_inte_smp.v
SRC_V  += doublediff.v serialize.v grab_channels.v

all: $(TARGET).vcd

%.v: %.py
	python3 $< build

vvm_dsp_tb: $(SRC_V)

$(TARGET)_tb: $(TARGET).v

plot: $(TARGET).vcd
	python3 quickPlot.py output.txt --skip 100 --fs 117.6e6

CLEAN += cordicg_b22.v output.txt dds.v vvm_dsp.v $(TARGET)_tb $(TARGET).vcd

include $(BUILD_DIR)/bottom_rules.mk
