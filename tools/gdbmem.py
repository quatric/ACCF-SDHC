"""Minimal GDB remote-serial-protocol client for Dolphin's GDB stub.

This Dolphin build is stock (no Felk scripting fork), so the mcp-dolphin bridge
can't be loaded -- but the GDB stub on port 2159 exposes memory just as well.
Used to confirm the SDHC patch is actually resident in MEM1 at runtime, not just
correct on disk.
"""
import socket, time, sys


class Gdb:
    def __init__(self, host='127.0.0.1', port=2159, timeout=15):
        self.s = socket.create_connection((host, port), timeout=timeout)
        self.s.settimeout(timeout)
        self._timeout = timeout
        self.buf = b''

    def _cksum(self, body):
        return sum(body) & 0xFF

    def send(self, body):
        b = body.encode()
        pkt = b'$' + b + b'#' + ('%02x' % self._cksum(b)).encode()
        self.s.sendall(pkt)

    def raw(self, data):
        self.s.sendall(data)

    def recv(self):
        """Read one packet, skipping acks."""
        while True:
            while b'$' not in self.buf or b'#' not in self.buf.split(b'$', 1)[1]:
                chunk = self.s.recv(4096)
                if not chunk:
                    raise EOFError('gdb stub closed')
                self.buf += chunk
            pre, rest = self.buf.split(b'$', 1)
            body, rest2 = rest.split(b'#', 1)
            if len(rest2) < 2:
                self.buf += self.s.recv(4096)
                continue
            self.buf = rest2[2:]
            self.s.sendall(b'+')
            return body.decode(errors='replace')

    def cmd(self, body):
        self.send(body)
        return self.recv()

    def drain(self, secs=0.4):
        """Swallow any unsolicited packets (e.g. a second stop reply after
        an interrupt) so the next request/response pair stays in step."""
        end = time.time() + secs
        self.s.settimeout(0.2)
        try:
            while time.time() < end:
                try:
                    chunk = self.s.recv(4096)
                    if not chunk:
                        break
                except socket.timeout:
                    break
        finally:
            self.s.settimeout(self._timeout)
        self.buf = b''

    def read_mem(self, addr, length):
        """m<addr>,<len> -- chunked, since stubs cap packet size.

        An empty reply means 'unsupported' in RSP, which here really means the
        stream desynced; resync and retry before giving up."""
        out = b''
        off = 0
        while off < length:
            n = min(256, length - off)
            r = None
            for attempt in range(3):
                r = self.cmd('m%x,%x' % (addr + off, n))
                if r and not r.startswith('E'):
                    break
                time.sleep(0.2)
                self.drain(0.2)
            if not r or r.startswith('E'):
                raise RuntimeError('read %08X+%X failed: %r' % (addr + off, n, r))
            out += bytes.fromhex(r)
            off += n
        return out

    def interrupt(self):
        self.raw(b'\x03')
        time.sleep(0.5)
        try:
            r = self.recv()
        except Exception:
            r = None
        self.drain(0.5)
        return r

    def cont(self):
        self.send('c')

    def close(self):
        try:
            self.s.close()
        except Exception:
            pass


if __name__ == '__main__':
    g = Gdb()
    print('connected; stub says:', g.cmd('?'))
    for a in sys.argv[1:]:
        addr = int(a, 16)
        print('%08X: %s' % (addr, g.read_mem(addr, 32).hex().upper()))
    g.close()
