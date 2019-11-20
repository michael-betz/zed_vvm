from sys import argv, exit
from litex.soc.integration.builder import Builder
from litex import RemoteClient
from os import system
from os.path import isfile, splitext
from struct import pack, unpack
# from numpy import *
# from matplotlib.pyplot import *
# from scipy.signal import *
from migen import *


class LedBlinker(Module):
    def __init__(self, f_clk=100e6, outs=None):
        """
        for debugging clocks
        toggles outputs at 1 Hz
        use ClockDomainsRenamer()!
        """
        self.outs = outs
        if outs is None:
            self.outs = Signal(8)

        ###

        max_cnt = int(f_clk / 2)
        cntr = Signal(max=max_cnt + 1)
        self.sync += [
            cntr.eq(cntr + 1),
            If(cntr == max_cnt,
                cntr.eq(0),
                self.outs.eq(Cat(~self.outs[-1], self.outs[:-1]))
            )
        ]


def main(soc, doc='', **kwargs):
    """ generic main function for litex modules """
    print(argv, kwargs)
    if len(argv) < 2:
        print(doc)
        exit(-1)
    tName = argv[0].replace(".py", "")
    vns = None
    if 'sim' in argv:
        run_simulation(
            soc,
            vcd_name=tName + '.vcd',
            **kwargs
        )
    if "build" in argv:
        builder = Builder(
            soc, output_dir="build", csr_csv="build/csr.csv",
            csr_json="build/csr.json",
            compile_gateware=False, compile_software=False
        )
        vns = builder.build(
            build_name=tName, regular_comb=False, blocking_assign=True
        )
        # Ugly workaround as I couldn't get vpath to work :(
        system('cp ./build/gateware/mem*.init .')
    if "synth" in argv:
        builder = Builder(
            soc, output_dir="build", csr_csv="build/csr.csv",
            csr_json="build/csr.json",
            compile_gateware=True, compile_software=True
        )
        vns = builder.build(build_name=tName)
    if "config" in argv:
        prog = soc.platform.create_programmer()
        prog.load_bitstream("build/gateware/{:}.bit".format(tName))
    print(vns)
    try:
        soc.do_exit(vns)
    except:
        pass
    return vns


# -----------------------
#  litex_server stuff
# -----------------------
def getId(r):
    s = ""
    for i in range(64):
        temp = r.read(r.bases.identifier_mem + i * 4)
        if temp == 0:
            break
        s += chr(temp & 0xFF)
    return s


def conLitexServer(csr_csv="build/csr.csv", port=1234):
    for i in range(32):
        try:
            r = RemoteClient(csr_csv=csr_csv, debug=False, port=port + i)
            r.open()
            print("Connected to Port", 1234 + i)
            break
        except ConnectionRefusedError:
            r = None
    if r:
        print(getId(r))
    else:
        print("Could not connect to RemoteClient")
    return r


def myzip(*vals):
    """
    interleave elements in a flattened list

    >>> myzip([1,2,3], ['a', 'b', 'c'])
    [1, 'a', 2, 'b', 3, 'c']
    """
    return [i for t in zip(*vals) for i in t]


def unique_filename(file_name):
    """ thank you stack overflow """
    counter = 1
    ps = splitext(file_name)  # returns ('/path/file', '.ext')
    while isfile(file_name):
        file_name = ps[0] + '_' + str(counter) + ps[1]
        counter += 1
    return file_name
