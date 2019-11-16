TARGET = hello_world

CC = arm-linux-gnueabi-gcc

CFLAGS += -I/home/michael/fpga_wsp/litex/litex/soc/software/include
CFLAGS += -I../../build/software/include

OBJS   = csr_lib.o i2c_soft.o

$(TARGET): $(OBJS)

clean:
	rm -f $(TARGET) $(OBJS)
