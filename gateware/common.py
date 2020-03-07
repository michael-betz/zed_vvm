from sys import argv, exit
from litex.soc.integration.builder import Builder
from os import system
from litex.soc.interconnect.csr import CSRStorage
from migen.genlib.cdc import PulseSynchronizer
# from numpy import *
# from matplotlib.pyplot import *
# from scipy.signal import *
from migen import *


def csr_helper(obj, name, regs, cdc=False, pulsed=False, **kwargs):
    '''
    handle csr + optional clock domain crossing (cdc) from sys to sample

    obj: the object where the csr will be pushed into

    cdc:    add a pulse synchronizer to move the csr write strobe to the
            sample domain, then use the strobe to latch csr.storage

    pulsed: instead of latching csr.storage in the sample clock domain,
            make its value valid only for one cycle and zero otherwise
    '''
    for i, reg in enumerate(regs):
        if type(regs) in (list, tuple) and len(regs) > 1:
            name += str(i)
        csr = CSRStorage(len(reg), name=name, **kwargs)
        setattr(obj, name, csr)
        if cdc:
            # csr.storage is fully latched and stable when csr.re is pulsed
            # hence we only need to cross the csr.re pulse into the sample
            # clock domain and then latch csr.storage there once more
            ps = PulseSynchronizer('sys', 'sample')
            setattr(obj.submodules, name + '_sync', ps)
            obj.comb += ps.i.eq(csr.re)
            if pulsed:
                obj.sync.sample += reg.eq(Mux(ps.o, csr.storage, 0))
            else:
                obj.sync.sample += If(ps.o, reg.eq(csr.storage))
        else:
            if pulsed:
                obj.comb += reg.eq(Mux(csr.re, csr.storage, 0))
            else:
                obj.comb += reg.eq(csr.storage)


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


def myzip(*vals):
    """
    interleave elements in a flattened list

    >>> myzip([1,2,3], ['a', 'b', 'c'])
    [1, 'a', 2, 'b', 3, 'c']
    """
    return [i for t in zip(*vals) for i in t]
