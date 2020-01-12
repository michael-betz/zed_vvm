import socket, select

class SocketInstrument(object):
    '''
    socket replacement for visa.instrument class
    Allows to talk to SCPI instruments over ethernet sockets

    Changelog
    ----------
    29.3.2015   Ported to Py3

    mbetz@cern.ch
    '''

    def __init__( self, IPaddress, PortNumber, chunkSize=2**15, timeout=5.0 ):
        """ Startup the Socket. Please don't instantiate this class but use the "with"
        chunkSize = how many bytes to read in one go
        timeOut   = connection timeout in [s]
        usage:
        with Socket_Instrument("192.168.1.1",4242) as instr:
            print( instr.ask("*IDN?") )
        """
        self._chunkSize = chunkSize
        self._ip = IPaddress
        self._port = PortNumber
        self._timeout = timeout

    def __enter__(self):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.connect((self._ip, self._port))
        self.s.setblocking( False )
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def write(self, cmd):
        ba = bytearray(cmd+'\n','UTF-8')
        self.s.send( ba )

    def askF(self, cmd):
        """ Returns VISA result as float, works with echo on or off """
        respString = self.ask( cmd )
        strFrag = respString.split(" ")
        return float(strFrag[-1])

    def askB(self, cmd):
        """ Returns VISA result as Bytearray """
        self.write( cmd )
        resp = self.read()
        return resp

    def ask(self, cmd):
        """ Returns VISA result as String """
        return self.askB( cmd ).decode()

    def read(self):
        """ Returns VISA read as Bytearray """
        response = bytearray()
        while True:
            ready = select.select([self.s], [], [], self._timeout)  #Wait until data becomes availible (timeout)
            if len(ready[0]) == 0:                                  #We are in trouble, got no response after timeout
                raise IOError("read(): Timeout is over and we got still no data! Wake up scope, WAKE UP!")
            else:
                r = self.s.recv(self._chunkSize)
                response.extend( r )
                if response.endswith(b"\n\r") or response.endswith(b"\n"): #The scope hopefully terminates all transmission with \n\r
                    break
        return response.rstrip()

    def close(self):
#        print "Socket_Instrument(): closing %s"%( self._ip )
        return self.s.close()
