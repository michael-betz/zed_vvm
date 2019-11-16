import os
import pwd
import grp
import mmap


def drop_privileges(uid_name='nobody', gid_name='nogroup'):
    """ thank you again stack overflow!! """
    if os.getuid() != 0:
        # We're not root so, like, whatever dude
        return

    # Get the uid/gid from the name
    running_uid = pwd.getpwnam(uid_name).pw_uid
    running_gid = grp.getgrnam(gid_name).gr_gid

    # Remove group privileges
    os.setgroups([])

    # Try setting the new uid/gid
    os.setgid(running_gid)
    os.setuid(running_uid)

    # Ensure a very conservative umask
    os.umask(0o077)


class CommDevmem:
    def __init__(self, adr_offset=None, debug=False):
        self.debug = debug
        if adr_offset is None:
            adr_offset = 0
        self.adr_offset = adr_offset

    def open(self):
        if hasattr(self, "sysfs"):
            return
        self.sysfs = open("/dev/mem", "r+b")
        drop_privileges()
        self.sysfs.flush()
        self.mmap = mmap.mmap(
            self.sysfs.fileno(), 0x38000000, offset=self.adr_offset
        )

    def close(self):
        if not hasattr(self, "sysfs"):
            return
        self.mmap.close()
        del self.mmap
        self.sysfs.close()
        del self.sysfs

    def read(self, addr, length=None):
        data = []
        length_int = 1 if length is None else length
        if addr % 4 > 0:
            print("warning: un-aligned memory access", hex(addr))
        self.mmap.seek(addr)
        for i in range(length_int):
            value = int.from_bytes(self.mmap.read(4), byteorder="little")
            if self.debug:
                print("read {:08x} @ {:08x}".format(value, addr + 4 * i))
            if length is None:
                return value
            data.append(value)
        return data

    def write(self, addr, data):
        data = data if isinstance(data, list) else [data]
        self.mmap.seek(addr)
        for i, value in enumerate(data):
            self.mmap.write(value.to_bytes(4, byteorder="little"))
            if self.debug:
                print("write {:08x} @ {:08x}".format(value, addr + 4 * i))
