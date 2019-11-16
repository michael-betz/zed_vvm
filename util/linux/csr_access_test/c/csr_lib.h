#ifndef CSR_LIB_H
#define CSR_LIB_H

// Must match base_address in `add_axi_to_wishbone()`
#define MEM_OFFSET 0x40000000

void get_map(void);

unsigned get_word(unsigned csr_addr);

void set_word(unsigned csr_addr, unsigned val);

void print_ident(void);

void cleanup(void);

#endif
