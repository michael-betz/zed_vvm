# litex_server apps

These apps are supposed to run on a host PC.

They connect to litex_server, running on the zedboard, through ethernet.
This allows them to read and write registers remotely.
Even though litex_server is much slower than running software on the zedboard
directly, it is still very useful for debugging and development purposes.

To install litex_server on the zedboard,
copy the [`litex_server_light`](../linux_apps/misc/litex_server_light) onto it.

Then start it up like that:
```bash
sudo litex_server.py --devmem --devmem-offset 0x40000000"
```
Once installed, litex_server startup can be done remotely with `make server` from `zed_vvm/gateware` directory.

Then run one of the below apps ...

```bash
# try -h to list supported command line arguments
```
__scope_app.py__ displays live ADC samples in time and frequency domain

__vvm_app.py__ displays live phase and magnitude measurement results over time

__litescope_dump.py__ helper script to download logic analyzer traces

__client_dev_sheet.ipynb__ jupyter notebook sheet which was used for development

__cal__ worksheet and data which was used to carry out the phase / magnitude calibration


# remote litex_server
`linux_apps/misc/litex_server_light` contains a minimal version of which can run on the zedboard.
It only requires python3 installed. It needs sudo to open `/dev/mem`, so it is dangerous!
It then connects to the general purpose AXI master (gp0) at address 0x43c00000.
On the PL side, this is connected to an AXI to Wishbone converter to read and write the CSRs.

## GP0 address range
The Zynq general purpose AXI master interfaces are mapped to these addresses in memory

| Start     | End      | Size               | Interface |
| --------- | -------- | ------------------ | --------- |
| 4000_0000 | 7FFF_FFF | 3800_0000 (896 MB) | M_AXI_GP0 |
| 8000_0000 | BFFF_FFF | 3800_0000 (896 MB) | M_AXI_GP1 |

The AXI to wishbone adapter subtracts an offset (base_address) and removes the 2 LSB bits so we get word addresses.
See mapping below.

```python
self.add_axi_to_wishbone(self.axi_gp0, base_address=0x4000_0000)
```

| AXI (devmem) | WB << 2     | WB           |
| ------------ | ----------- | ------------ |
| 0x4000_0000  | 0x0000_0000 | 0x0000_0000  |
| 0x4000_0004  | 0x0000_0004 | 0x0000_0001  |
| 0x7FFF_FFFC  | 0x3FFF_FFFC | 0x0FFF_FFFF  |
