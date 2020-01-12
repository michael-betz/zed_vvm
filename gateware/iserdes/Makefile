SIM_PATH = $(dir $(shell which vivado))/../data/verilog/src
SIM_INCLUDES = -y . -y ./build/gateware -y $(SIM_PATH)/unisims

TARGET = s7_iserdes

all: $(TARGET).vcd

SRC_V += $(SIM_PATH)/glbl.v
SRC_V += $(TARGET).v
SRC_V += $(TARGET)_tb.v

# litex generate verilog
%.v: %.py
	python3 $< build

#--------------------------------------------
# xsim, due to ISERDESE2 being secured IP :(
#--------------------------------------------
$(TARGET)_tb: $(SRC_V)
	xvlog -nolog $(filter %.v,$^)
	xelab -nolog -L unisims_ver -L secureip $@ glbl -s $@ -timescale 1ns/1ns

$(TARGET).vcd: $(TARGET)_tb
	xsim -nolog -R $< -testplusarg vcd

clean:
	rm -rf $(TARGET).vcd webtalk* vivado.* xsim.dir .Xil *.pb *.jou
