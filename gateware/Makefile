TARGET = zed_vvm

all: $(TARGET).bit.bin

# litex generate verilog
%.v: %.py
	python3 $< build

# litex synthesize
build/gateware/%.bit: %.py ip/processing_system7_0.xci
	make -C dsp cordicg_b22.v
	python3 $< synth

# Convert .bit to .bit.bin which can be loaded from zedboard linux
# Also:
# Patch the PS register init .c file to make MOSI a normal GPIO
# (used by the encoder switch)
%.bit.bin: build/gateware/%.bit
	python3 build_tools/bitstream_fix.py $<
	cp $<.bin .
	(cd ip && \
	sed -i -e 's/EMIT_MASKWRITE(0XF800072C, 0x00003FFFU ,0x000007A0U),/EMIT_MASKWRITE(0XF800072C, 0x00003FFFU ,0x00001600U),/g' ps7_init.c && \
	sed -i -e 's/EMIT_MASKWRITE(0XF800072C, 0x00003FFFU ,0x000007A0U),/EMIT_MASKWRITE(0XF800072C, 0x00003FFFU ,0x00001600U),/g' ps7_init_gpl.c)

# Generate the viado IP file with zedboard config
ip/processing_system7_0.xci:
	(cd ip && \
	vivado -mode batch -source gen_ip.tcl && \
	ln -s zed_ps7.srcs/sources_1/ip/processing_system7_0/processing_system7_0.xci processing_system7_0.xci)

# Upload to the zedboard via scp and program the PL
upload:
	build_tools/remote_config_fpga.sh $(TARGET).bit.bin

# Start litex_server to read / write CSRs on FPGA
server:
	build_tools/remote_litex_server.sh

clean:
	rm -f $(TARGET).bit.bin
	rm -rf build
	rm -rf __pycache__
	rm -f mem.init
	rm -f mem_?.init

clean_ip:
	# delete EVERYTHING except gen_ip.tcl (a bit harsh, I know ...)
	mv ip/gen_ip.tcl .
	rm -rf ip/* ip/.Xil
	mv gen_ip.tcl ip

.PRECIOUS: build/gateware/zed_vvm.bit
