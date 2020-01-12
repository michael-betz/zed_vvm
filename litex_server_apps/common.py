from litex import RemoteClient
from os.path import isfile, splitext


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


def unique_filename(file_name):
    """ thank you stack overflow """
    counter = 1
    ps = splitext(file_name)  # returns ('/path/file', '.ext')
    while isfile(file_name):
        file_name = ps[0] + '_' + str(counter) + ps[1]
        counter += 1
    return file_name
