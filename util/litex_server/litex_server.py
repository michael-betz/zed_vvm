#!/usr/bin/env python3
import argparse
import time
import socket
import threading
from etherbone import EtherbonePacket, EtherboneRecord, EtherboneWrites
from etherbone import EtherboneIPC


class RemoteServer(EtherboneIPC):
    def __init__(self, comm, bind_ip, bind_port=1234):
        self.comm = comm
        self.bind_ip = bind_ip
        self.bind_port = bind_port
        self.lock = False

    def open(self):
        if hasattr(self, "socket"):
            return
        socket_flags = 0
        if hasattr(socket, "SO_REUSEADDR"):
            socket_flags = socket_flags | socket.SO_REUSEADDR
        if hasattr(socket, "SO_REUSEPORT"):
            socket_flags = socket_flags | socket.SO_REUSEPORT
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket_flags, 1)
        self.socket.bind((self.bind_ip, self.bind_port))
        print("tcp port: {:d}".format(self.bind_port))
        self.socket.listen(1)
        self.comm.open()

    def close(self):
        self.comm.close()
        if not hasattr(self, "socket"):
            return
        self.socket.close()
        del self.socket

    def _serve_thread(self):
        while True:
            client_socket, addr = self.socket.accept()
            print("Connected with " + addr[0] + ":" + str(addr[1]))
            try:
                while True:
                    try:
                        packet = self.receive_packet(client_socket)
                        if packet == 0:
                            break
                    except Exception:
                        break
                    packet = EtherbonePacket(packet)
                    packet.decode()

                    record = packet.records.pop()

                    # wait for lock
                    while self.lock:
                        time.sleep(0.01)

                    # set lock
                    self.lock = True

                    # handle writes:
                    if record.writes is not None:
                        self.comm.write(
                            record.writes.base_addr, record.writes.get_datas()
                        )

                    # handle reads
                    if record.reads is not None:
                        reads = []
                        for addr in record.reads.get_addrs():
                            reads.append(self.comm.read(addr))

                        record = EtherboneRecord()
                        record.writes = EtherboneWrites(datas=reads)
                        record.wcount = len(record.writes)

                        packet = EtherbonePacket()
                        packet.records = [record]
                        packet.encode()
                        self.send_packet(client_socket, packet)

                    # release lock
                    self.lock = False

            finally:
                print("Disconnect")
                client_socket.close()

    def start(self, nthreads):
        for i in range(nthreads):
            self.serve_thread = threading.Thread(target=self._serve_thread)
            self.serve_thread.setDaemon(True)
            self.serve_thread.start()


def main():
    print("LiteX remote server")
    parser = argparse.ArgumentParser()
    # Common arguments
    parser.add_argument("--bind-ip", default="localhost",
                        help="Host bind address")
    parser.add_argument("--bind-port", default=1234,
                        help="Host bind port")

    # Devmem arguments
    parser.add_argument("--devmem", action="store_true",
                        help="Select /dev/mem interface")
    parser.add_argument(
        "--devmem-offset",
        default=0x40000000,
        type=lambda x: int(x, 0),
        help="/dev/mem address offset, gp0 is at 0x4000_0000"
    )

    args = parser.parse_args()

    if args.devmem:
        from comm_devmem import CommDevmem
        print(
            "[CommDevmem] /dev/mem @ {:x}/ ".format(args.devmem_offset),
            end="",
            flush=True
        )
        comm = CommDevmem(args.devmem_offset)
    else:
        parser.print_help()
        exit()

    server = RemoteServer(comm, args.bind_ip, int(args.bind_port))
    server.open()
    server.start(4)
    while True:
        time.sleep(1000)


if __name__ == "__main__":
    main()
