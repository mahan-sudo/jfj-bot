"""
⚠️ فقط برای تست! جایگزین سبکِ psycopg2 (پروتکل ساده‌ی PostgreSQL، فقط پایتون خالص).
در سندباکس تست pip اجازه‌ی نصب psycopg2 نداشت؛ این فایل همان زیرمجموعه‌ی API را که db.py استفاده می‌کند
روی یک PostgreSQL 16 واقعی پیاده می‌کند تا همه‌ی SQLها روی سرور واقعی اجرا شوند. در محیط واقعی (Railway/VPS)
psycopg2-binary نصب می‌شود و این پوشه استفاده نمی‌شود (فقط وقتی tests/shim در sys.path باشد).
"""
import socket, struct, re, decimal, os
from urllib.parse import urlparse, unquote, parse_qs
from . import extensions  # noqa

__version__ = "shim-0"
paramstyle = "pyformat"
extensions = extensions


class Error(Exception):
    pgcode = None
    pgerror = None


class Warning(Exception):
    pass


class InterfaceError(Error): pass
class DatabaseError(Error): pass
class DataError(DatabaseError): pass
class OperationalError(DatabaseError): pass
class IntegrityError(DatabaseError): pass
class InternalError(DatabaseError): pass
class ProgrammingError(DatabaseError): pass
class NotSupportedError(DatabaseError): pass


def _err_class(code):
    c = (code or "")[:2]
    return {"23": IntegrityError, "22": DataError, "42": ProgrammingError, "08": OperationalError,
            "53": OperationalError, "55": OperationalError, "57": OperationalError, "40": OperationalError,
            "25": InternalError}.get(c, DatabaseError)


def _lit(v):
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if v != v or v in (float("inf"), float("-inf")):
            return "'%s'::float8" % repr(v)
        return repr(v)
    if isinstance(v, decimal.Decimal):
        return str(v)
    if isinstance(v, (bytes, bytearray, memoryview)):
        return "'\\x%s'::bytea" % bytes(v).hex()
    if isinstance(v, (list, tuple)):
        return "(" + ",".join(_lit(x) for x in v) + ")"
    s = str(v)
    if "\x00" in s:
        raise DataError("A string literal cannot contain NUL (0x00) characters.")
    return "'" + s.replace("'", "''") + "'"


def _bind(sql, params):
    if params is None:
        return sql
    if isinstance(params, dict):
        raise NotSupportedError("shim: dict params")
    out, i, n = [], 0, 0
    params = tuple(params)
    while i < len(sql):
        ch = sql[i]
        if ch == "%" and i + 1 < len(sql):
            nx = sql[i + 1]
            if nx == "s":
                if n >= len(params):
                    raise ProgrammingError("not enough arguments for format string")
                out.append(_lit(params[n])); n += 1; i += 2; continue
            if nx == "%":
                out.append("%"); i += 2; continue
            raise ProgrammingError("unsupported format character %r" % nx)
        out.append(ch); i += 1
    if n != len(params):
        raise ProgrammingError("not all arguments converted during string formatting")
    return "".join(out)


class _Desc(tuple):
    @property
    def name(self): return self[0]
    @property
    def type_code(self): return self[1]


class Cursor:
    def __init__(self, conn):
        self.connection = conn
        self._rows = []
        self._pos = 0
        self.description = None
        self.rowcount = -1
        self.arraysize = 1
        self.closed = False

    def execute(self, sql, params=None):
        if self.closed:
            raise InterfaceError("cursor already closed")
        c = self.connection
        if c.closed:
            raise InterfaceError("connection already closed")
        if params is not None and not params and "%" not in sql:
            params = None
        q = _bind(sql, params) if params is not None else sql
        if not c.autocommit and c._status == "I":
            c._simple("BEGIN")
        res = c._simple(q)
        self.description, self._rows, self.rowcount = res
        self._pos = 0
        return None

    def executemany(self, sql, seq):
        n = 0
        for p in seq:
            self.execute(sql, p)
            n += max(self.rowcount, 0)
        self.rowcount = n

    def fetchone(self):
        if self.description is None:
            raise ProgrammingError("no results to fetch")
        if self._pos >= len(self._rows):
            return None
        r = self._rows[self._pos]; self._pos += 1
        return r

    def fetchmany(self, size=None):
        size = size or self.arraysize
        r = self._rows[self._pos:self._pos + size]; self._pos += len(r)
        return r

    def fetchall(self):
        if self.description is None:
            raise ProgrammingError("no results to fetch")
        r = self._rows[self._pos:]; self._pos = len(self._rows)
        return r

    def __iter__(self):
        while True:
            r = self.fetchone()
            if r is None:
                return
            yield r

    def close(self):
        self.closed = True

    def __enter__(self): return self
    def __exit__(self, *a): self.close()


_INT = {20, 21, 23, 26}
_FLT = {700, 701}


class Connection:
    def __init__(self, host, port, user, dbname, options=None, password=None, timeout=10, app=None):
        self.autocommit = False
        self.closed = 0
        self._status = "I"
        self._buf = b""
        try:
            self._s = socket.create_connection((host, port), timeout=timeout)
        except OSError as e:
            raise OperationalError("could not connect to server: %s" % e)
        self._s.settimeout(None)
        self._s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        params = {"user": user, "database": dbname, "client_encoding": "UTF8"}
        if options:
            params["options"] = options
        if app:
            params["application_name"] = app
        body = struct.pack("!i", 196608) + b"".join(k.encode() + b"\0" + v.encode() + b"\0" for k, v in params.items()) + b"\0"
        self._s.sendall(struct.pack("!i", len(body) + 4) + body)
        while True:
            t, p = self._read()
            if t == b"R":
                code = struct.unpack("!i", p[:4])[0]
                if code != 0:
                    self.close()
                    raise OperationalError("shim supports only trust auth (got auth code %d)" % code)
            elif t == b"E":
                self.close()
                raise self._mkerr(p, OperationalError)
            elif t == b"Z":
                self._status = p.decode()
                break

    # --- low level
    def _recv(self, n):
        while len(self._buf) < n:
            try:
                d = self._s.recv(65536)
            except OSError as e:
                self.closed = 2
                raise OperationalError("connection lost: %s" % e)
            if not d:
                self.closed = 2
                raise OperationalError("server closed the connection unexpectedly")
            self._buf += d
        r, self._buf = self._buf[:n], self._buf[n:]
        return r

    def _read(self):
        h = self._recv(5)
        t, ln = h[:1], struct.unpack("!i", h[1:])[0]
        return t, self._recv(ln - 4)

    @staticmethod
    def _fields(p):
        d = {}
        for part in p.split(b"\0"):
            if part:
                d[part[:1].decode()] = part[1:].decode("utf-8", "replace")
        return d

    def _mkerr(self, p, default=None):
        f = self._fields(p)
        e = (_err_class(f.get("C")) if default is None or f.get("C") else default)(f.get("M", "error"))
        e.pgcode = f.get("C")
        e.pgerror = f.get("M")
        e.diag = f
        return e

    def _simple(self, q):
        if self.closed:
            raise InterfaceError("connection already closed")
        data = q.encode("utf-8") + b"\0"
        try:
            self._s.sendall(b"Q" + struct.pack("!i", len(data) + 4) + data)
        except OSError as e:
            self.closed = 2
            raise OperationalError("connection lost: %s" % e)
        desc, rows, rc, err, cols = None, [], -1, None, None
        while True:
            t, p = self._read()
            if t == b"T":
                n = struct.unpack("!h", p[:2])[0]
                off, cols, desc = 2, [], []
                for _ in range(n):
                    e = p.index(b"\0", off)
                    name = p[off:e].decode()
                    tbl, col, oid, sz, mod, fmt = struct.unpack("!ihihih", p[e + 1:e + 19])
                    cols.append(oid)
                    desc.append(_Desc((name, oid, None, sz, None, None, None)))
                    off = e + 19
                desc = tuple(desc)
                rows = []
            elif t == b"D":
                n = struct.unpack("!h", p[:2])[0]
                off, row = 2, []
                for i in range(n):
                    ln = struct.unpack("!i", p[off:off + 4])[0]; off += 4
                    if ln == -1:
                        row.append(None)
                    else:
                        row.append(self._cast(cols[i], p[off:off + ln])); off += ln
                rows.append(tuple(row))
            elif t == b"C":
                tag = p.rstrip(b"\0").decode().split()
                if tag and tag[-1].isdigit() and tag[0] in ("INSERT", "UPDATE", "DELETE", "SELECT", "MERGE", "MOVE", "FETCH", "COPY"):
                    rc = int(tag[-1])
                elif tag and tag[0] not in ("INSERT", "UPDATE", "DELETE", "SELECT"):
                    rc = -1
            elif t == b"E":
                err = self._mkerr(p)
            elif t == b"Z":
                self._status = p.decode()
                break
            # N, S, I, etc: ignore
        if err:
            raise err
        if desc is None:
            return None, [], rc
        return desc, rows, (len(rows) if rc < 0 else rc)

    @staticmethod
    def _cast(oid, b):
        c = extensions._CASTERS.get(oid)
        s = b.decode("utf-8")
        if c is not None:
            return c(s, None)
        if oid in _INT:
            return int(s)
        if oid in _FLT:
            return float(s)
        if oid == 1700:
            return decimal.Decimal(s)
        if oid == 16:
            return s == "t"
        if oid == 17:
            return bytes.fromhex(s[2:]) if s.startswith("\\x") else s.encode()
        return s

    # --- API
    def cursor(self, *a, **k):
        return Cursor(self)

    def commit(self):
        if self._status != "I" and not self.closed:
            self._simple("COMMIT")

    def rollback(self):
        if self._status != "I" and not self.closed:
            self._simple("ROLLBACK")

    def close(self):
        if self.closed:
            return
        try:
            self._s.sendall(b"X" + struct.pack("!i", 4))
        except OSError:
            pass
        try:
            self._s.close()
        except OSError:
            pass
        self.closed = 1

    def get_transaction_status(self):
        return {"I": 0, "T": 2, "E": 3}.get(self._status, 1)

    @property
    def status(self):
        return 1 if self._status != "I" else 0


def connect(dsn=None, **kw):
    host, port, user, db, opts = kw.get("host"), kw.get("port"), kw.get("user"), kw.get("dbname") or kw.get("database"), kw.get("options")
    if dsn:
        if "://" in dsn:
            u = urlparse(dsn)
            host, port, user = u.hostname, u.port, unquote(u.username) if u.username else None
            db = (u.path or "/").lstrip("/") or None
            q = parse_qs(u.query)
            if "options" in q:
                opts = q["options"][0]
        else:
            for part in re.findall(r"(\w+)\s*=\s*('(?:[^'\\]|\\.)*'|\S+)", dsn):
                k, v = part[0], part[1].strip("'")
                if k == "host": host = v
                elif k == "port": port = int(v)
                elif k == "user": user = v
                elif k in ("dbname", "database"): db = v
                elif k == "options": opts = v
    return Connection(host or "127.0.0.1", int(port or 5432), user or "postgres", db or user or "postgres", opts,
                      timeout=kw.get("connect_timeout", 10), app=kw.get("application_name"))
