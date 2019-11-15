#include "i2c_soft.h"
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <unistd.h>
#include "csr_lib.h"
#include "generated/csr.h"


//-------------------------------------------------
// Private macros /functions
//-------------------------------------------------
// setting / clearing / reading the I2C pins
static unsigned i2c_reg;

static void commit(void) {
    set_word(CSR_SI570_I2C_W_ADDR, i2c_reg);
    usleep(1);
}

static void SDA1(void) {
    i2c_reg &= ~(1 << CSR_SI570_I2C_W_OE_OFFSET);
    commit();
}

static void SDA0(void) {
    i2c_reg |= (1 << CSR_SI570_I2C_W_OE_OFFSET);
    commit();
}

static bool SDAR(void) { return get_word(CSR_SI570_I2C_R_ADDR); }

static void SCL0(void) {
    i2c_reg &= ~(1 << CSR_SI570_I2C_W_SCL_OFFSET);
    commit();
}

static void SCL1(void) {
    i2c_reg |= (1 << CSR_SI570_I2C_W_SCL_OFFSET);
    commit();
}

//-------------------------------------------------
// Low level functions
//-------------------------------------------------
void i2c_init(void) {
    // I2C pin signals alternate between 0 and Z, so clear the gpioOut bits
    i2c_reg = (1 << CSR_SI570_I2C_W_SCL_OFFSET) |
              (0 << CSR_SI570_I2C_W_SDA_OFFSET) |
              (0 << CSR_SI570_I2C_W_OE_OFFSET);
    commit();
}

void i2c_stop(void) {
    SDA0();
    SCL1();
    SDA1();
}

void i2c_start(void) {
    SCL1();
    SDA0();
    SCL0();
}

int i2c_tx(uint8_t dat) {
    for (unsigned i=0; i<=7; i++) {
        if (dat & 0x80) {
            SDA1();
        } else {
            SDA0();
        }
        SCL1();
        dat <<= 1;
        SCL0();
    }
    // Receive ack from slave
    SDA1();
    SCL1();
    int ack = SDAR() == 0;
    SCL0();
    return ack;
}

uint8_t i2c_rx( int ack ){
    uint8_t dat = 0;
    // TODO check for clock stretching here
    for (unsigned i=0; i<=7; i++) {
        dat <<= 1;
        SCL1();
        dat |= SDAR();
        SCL0();
    }
    // Send ack to slave
    SCL0();
    if (ack) {
        SDA0();
    } else {
        SDA1();
    }
    SCL1();
    SCL0();
    SDA1();
    return dat;
}

//-------------------------------------------------
// High level functions (dealing with registers)
//-------------------------------------------------
int i2c_write_regs(uint8_t i2cAddr, uint8_t regAddr, uint8_t *buffer, uint16_t len) {
    int ret=1;
    i2c_start();
    ret &= i2c_tx((i2cAddr << 1) | I2C_W);
    ret &= i2c_tx(regAddr);
    while (len-- > 0) {
        ret &= i2c_tx(*buffer++);
    }
    i2c_stop();
    return ret;
}

int i2c_write_reg(uint8_t i2cAddr, uint8_t regAddr, uint8_t val) {
    return i2c_write_regs(i2cAddr, regAddr, &val, 1);
}

int i2c_read_regs(uint8_t i2cAddr, uint8_t regAddr, uint8_t *buffer, uint16_t len) {
    int ret=1;
    i2c_start();
    ret &= i2c_tx((i2cAddr<<1) | I2C_W);
    ret &= i2c_tx(regAddr );
    i2c_start();                        // Repeated start to switch to read mode
    ret &= i2c_tx( (i2cAddr<<1) | I2C_R);
    while ( len-- > 0 ){
        *buffer++ = i2c_rx(len != 0);   // Send NACK for the last byte
    }
    i2c_stop();
    return ret;
}

//-------------------------------------------------
// Debugging functions (print stuff to uart)
//-------------------------------------------------
void i2c_scan(void) {
    printf("I2C scan: [");
    for (unsigned i=0; i<=127; i++) {
        i2c_start();
        int ret = i2c_tx((i<<1) | I2C_W);
        if(ret) {
            printf("%02x ", i);
        }
        i2c_stop();
    }
    printf("]\n");
}

int i2c_dump(uint8_t i2cAddr, uint8_t regAddr, int nBytes) {
    int ret=1;
    i2c_start();
    ret &= i2c_tx((i2cAddr<<1) | I2C_W);
    ret &= i2c_tx(regAddr);
    i2c_start();                          // Repeated start to switch to read mode
    ret &= i2c_tx((i2cAddr<<1) | I2C_R);
    if (!ret) {
        printf("I2C Error\n");
        return ret;
    }
    for (int i=0; i<nBytes; i++) {
        if ((nBytes > 16) && ((i % 16) == 0)) {
            printf("\n    ");
            printf("%04x", i + regAddr);
            printf(": ");
        }
        printf("%02x", i2c_rx(i < (nBytes-1)));    // Send NACK for the last byte
        printf(" ");
    }
    i2c_stop();
    return ret;
}

int i2c_read_ascii(uint8_t i2cAddr, uint8_t regAddr, int nBytes) {
    int ret=1;
    i2c_start();
    ret &= i2c_tx((i2cAddr<<1) | I2C_W);
    ret &= i2c_tx(regAddr);
    i2c_start();                     // Repeated start to switch to read mode
    ret &= i2c_tx((i2cAddr<<1) | I2C_R);
    while (nBytes-- > 0){
        putchar(i2c_rx(nBytes != 0));   // Send NACK for the last byte
    }
    i2c_stop();
    return ret;
}
