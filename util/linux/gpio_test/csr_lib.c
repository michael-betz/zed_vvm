#include "csr_lib.h"
#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <fcntl.h>
#include <unistd.h>
#include "generated/csr.h"
#include "generated/mem.h"


// Global memory map pointer
static unsigned *g_map = NULL;
static int g_fdmem = -1;

unsigned get_word(unsigned csr_addr) {
	return g_map[csr_addr / 4];
}

void set_word(unsigned csr_addr, unsigned val) {
	g_map[csr_addr / 4] = val;
}

void print_ident(void)
{
	unsigned *p = g_map + CSR_IDENTIFIER_MEM_BASE / 4;
	char c;
	for (int i=0; i<64; i++) {
		c = (char)*p++;
		if (c == '\0')
			break;
		putchar(c);
	}
	putchar('\n');
}

void get_map(void)
{
	g_fdmem = open("/dev/mem", O_RDWR | O_SYNC);
	if (g_fdmem < 0) {
		printf("Failed to open the /dev/mem !\n");
		exit(-1);
	}
	g_map = (unsigned *)(mmap(
		NULL,
		CSR_SIZE / 4,
		PROT_READ | PROT_WRITE,
		MAP_SHARED,
		g_fdmem,
		MEM_OFFSET
	));
	if (g_map == NULL) {
		printf("Error mapping memory!\n");
		cleanup();
		exit(-1);
	}
}

void cleanup(void)
{
	munmap(g_map, CSR_SIZE / 4);
	close(g_fdmem);
}
