"""M2Crypto wrapper for OpenSSL BIO API.

Copyright (c) 1999, 2000 Ng Pheng Siong. All rights reserved."""

RCS_id='$Id: BIO.py,v 1.6 2000/11/08 14:36:16 ngps Exp $'

# 5 Nov 00: Unit testing and refactoring in progress...

import m2

m2.bio_init()

class BIO:

    """Generic class wrapper for the BIO API."""

    def __init__(self):
        self.closed = 0
        self.write_closed = 0

    def __del__(self):
        m2.bio_free(self.bio)

    def _ptr(self):
        return self.bio

    # Deprecated.
    bio_ptr = _ptr

    def fileno(self):
        return m2.bio_get_fd(self.bio)

    def readable(self):
        return not self.closed

    def read(self, size=4096):
        if not self.readable():
            raise IOError, 'cannot read'
        if size == 0:
            return ''
        elif size < 0:
            raise ValueError, 'read count is negative'
        return m2.bio_read(self.bio, size)

    def readline(self, size=1024):
        if not self.readable():
            raise IOError, 'cannot read'
        buf = m2.bio_gets(self.bio, size)
        if buf is None:
            return ''
        return buf

    def readlines(self, sizehint='ignored'):
        if not self.readable():
            raise IOError, 'cannot read'
        lines=[]
        while 1:
            buf=m2.bio_gets(self.bio, 1024)
            if buf is None:
                break
            lines.append(buf)
        return lines

    def writeable(self):
        return (not self.closed) and (not self.write_closed)
       
    def write(self, data):
        if not self.writeable():
            raise IOError, 'cannot write'
        return m2.bio_write(self.bio, data)

    def write_close(self):
        self.write_closed = 1

    def flush(self):
        m2.bio_flush(self.bio)

    def reset(self):
        raise NotImplementedError

    def close(self):
        self.closed = 1


class MemoryBuffer(BIO):

    """Class wrapper for BIO_s_mem. 
    
    Empirical testing suggests that this class performs less well than cStringIO, 
    because cStringIO is implemented in C, whereas this class is implemented in 
    Python. Thus, the recommended practice is to use cStringIO for regular work and 
    convert said cStringIO object to a MemoryBuffer object only when necessary."""

    def __init__(self, data=None):
        BIO.__init__(self)
        self.bio = m2.bio_new(m2.bio_s_mem())
        self._pyfree = 1
        if data is not None:
            m2.bio_write(self.bio, data)

    def __len__(self):
        return m2.bio_ctrl_pending(self.bio)

    def read(self, size=0):
        if not self.readable():
            raise IOError, 'cannot read'
        if size:
            return m2.bio_read(self.bio, size)
        else:
            return m2.bio_read(self.bio, m2.bio_ctrl_pending(self.bio))
            
    # Backwards-compatibility.
    getvalue = read_all = read

    def write_close(self):
        self.write_closed = 1
        m2.bio_set_mem_eof_return(self.bio, 0)


class File(BIO):

    """Class wrapper for BIO_s_fp. 
    
    This class interfaces Python to OpenSSL functions that expect BIO *. For
    general file manipulation in Python, use Python's builtin file object."""

    def __init__(self, pyfile, close_pyfile=1):
        BIO.__init__(self)
        self.pyfile = pyfile
        self.close_pyfile = close_pyfile
        self.bio = m2.bio_new_fp(pyfile, 0)

    def close(self):
        self.closed = 1
        if self.close_pyfile:
            self.pyfile.close()

def openfile(filename, mode='rb'):
    return File(open(filename, mode))


class IOBuffer(BIO):

    """Class wrapper for BIO_f_buffer. 
    
    Its principal function is to be BIO_push()'ed on top of a BIO_f_ssl, so
    that makefile() of said underlying SSL socket works."""

    def __init__(self, bio_ptr, mode='rw', _pyfree=1):
        BIO.__init__(self)
        self.io = m2.bio_new(m2.bio_f_buffer())
        self.bio = m2.bio_push(self.io, bio_ptr)
        if 'w' in mode:
            self.write_closed = 0
        else:
            self.write_closed = 1
        self._pyfree = _pyfree

    def __del__(self):
        if self._pyfree:
            m2.bio_pop(self.bio)
            m2.bio_free(self.io)


class CipherFilter(BIO):

    """Class wrapper for BIO_f_cipher."""

    def __init__(self, obio):
        BIO.__init__(self)
        self.obio = obio
        self.bio = m2.bio_new(m2.bio_f_cipher())
        self.closed = 0

    def __del__(self):
        if not self.closed:
            self.close()

    def close(self):
        m2.bio_pop(self.bio)
        m2.bio_free(self.bio)
        self.closed = 1
        
    def write_close(self):
        self.obio.write_close()

    def set_cipher(self, algo, key, iv, op):
        cipher = getattr(m2, algo)
        if not cipher:
            raise ValueError, ('unknown cipher', algo)
        m2.bio_set_cipher(self.bio, cipher(), key, iv, op) 
        m2.bio_push(self.bio, self.obio._ptr())


