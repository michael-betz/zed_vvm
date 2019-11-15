// Got stuck setting the Frequency of an Si570
// I2C transfer needs to be quick as the chip times
// out after 10 ms and reverts to default values.
// Using bit-bang I2C through litex_server with
// dev_mem access in python takes SECONDS!!!
//
// Trying to find the bottleneck.

#include <stdio.h>
#include "csr_lib.h"
#include "i2c_soft.h"
#include "generated/csr.h"
#include "generated/mem.h"

int main(int argc, char *argv[])
{
	get_map();

	print_ident();

	printf("SCRATCH: %08x\n", get_word(CSR_CTRL_SCRATCH_ADDR));
	set_word(CSR_CTRL_SCRATCH_ADDR, 0xAFFEDEAD);
	printf("SCRATCH: %08x\n", get_word(CSR_CTRL_SCRATCH_ADDR));

	// printf("GPIO toggle test ...\n");
	// for (int i=0; i<0x00100000; i++) {
	// 	set_word(CSR_SI570_SI570_OE_ADDR, 0);
	// 	set_word(CSR_SI570_SI570_OE_ADDR, 1);
	// }
	// Scope says 2.8 MHz ... Not bad ...
	// So why the h*** is litex_server so slow??

	// printf("Soft I2C test ...\n");
	// i2c_init();
	// i2c_scan();
	// i2c_dump(0x55, 0, 32);

	printf("\nSi570 setup ...\n");
	#define FREEZE_DCO_REG 		137
	#define SI570_FREEZE_DCO 	(1 << 4)
	#define CTRL_REG 			135
	#define SI570_NEW_FREQ 		(1 << 6)

	uint8_t setup1[] = {0xad, 0x42, 0xa8, 0xb2, 0x60, 0x6c};
	uint8_t setup2[] = {0xA0, 0xC2, 0xF4, 0x54, 0x6B, 0x22};

	i2c_write_reg(0x55, FREEZE_DCO_REG, SI570_FREEZE_DCO);
	if (argc == 1)
		i2c_write_regs(0x55, 0x0D, setup1, 6);
	if (argc == 2)
		i2c_write_regs(0x55, 0x0D, setup2, 6);
	i2c_write_reg(0x55, FREEZE_DCO_REG, 0);
	i2c_write_reg(0x55, CTRL_REG, SI570_NEW_FREQ);

	// i2c_dump(0x55, 0, 32);

	cleanup();
	printf("Done!\n");
	return 0;
}
