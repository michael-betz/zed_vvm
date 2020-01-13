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

Then run one of the below apps, use `-h` to get further information ...

__scope_app.py__ displays live time-domain samples as read from the ADC

__vvm_app.py__ displays live phase and magnitude measurement results

__litescope_dump.py__ helper script to download logic analyzer traces

__client_dev_sheet.ipynb__ jupyter notebook sheet which was used for development

__cal__ worksheet and data which was used to carry out the phase / magnitude calibration
