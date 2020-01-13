# linux_apps

These are mostly python applications which are supposed to run on the zedboard.

__vvm_daemon.py__ daemon application to setup and use the VVM. Measurement data and parameters are exported as mqtt topics.

__vvm_oled.py__ handles the front-panel OLED display and user interface, connects to vvm_daemon.py through mqtt.

__misc/vvmd.service__ systemd configuration for auto-starting the mqtt daemon. Copy to `/lib/systemd/system/` and enable with `sudo systemctl start vvmd`

__lib__ various helper classes to access CSRs from python without litex_server

__misc/csr_from_c__ helper library to access CSRs form C on the Zedboard. Superfast!!! (2 MHz gpio toggle)

__misc/litex_server_light__ a stripped down version of litex_server which can run on the Zedboard. No dependencies.

__misc/oled_experiments__ various experiments on how to utilize pygame to implement the OLED user interface

