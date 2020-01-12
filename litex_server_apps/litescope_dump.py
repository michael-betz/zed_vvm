#!/usr/bin/env python3
from litex import RemoteClient
from litescope import LiteScopeAnalyzerDriver
import sys
sys.path.append("..")
from common import *

r = conLitexServer()

# # #

analyzer = LiteScopeAnalyzerDriver(r.regs, "analyzer", config_csv="build/analyzer.csv", debug=True)
analyzer.configure_subsampler(1)
analyzer.configure_group(0)
try:
	trig = sys.argv[1]
except Exception:
	trig = "user_btn_u"
print("Trigger:", trig)
analyzer.add_rising_edge_trigger(trig)
analyzer.run(offset=32, length=64)
analyzer.wait_done()
analyzer.upload()
analyzer.save("dump.vcd")

# # #

r.close()
