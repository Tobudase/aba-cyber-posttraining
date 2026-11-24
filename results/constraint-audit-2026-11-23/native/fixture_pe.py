import struct
def pe(path,v):
    # Readable PE32 headers and an empty, non-executable data section. No code.
    data=bytearray(1024)
    data[:2]=b'MZ'
    struct.pack_into('<I',data,0x3c,128)
    data[128:132]=b'PE\0\0'
    struct.pack_into('<HHIIIHH',data,132,0x14c,1,0,0,0,224,0x0102)
    o=152
    struct.pack_into('<H',data,o,0x10b)
    for off,num in ((28,0x400000),(32,4096),(36,512),(56,8192),(60,512),(92,16)):
        struct.pack_into('<I',data,o+off,num)
    struct.pack_into('<HH',data,o+68,3,0x140 if v else 0)
    data[376:384]=b'.data\0\0\0'
    struct.pack_into('<IIII',data,384,4,4096,512,512)
    struct.pack_into('<I',data,412,0x40000040)
    path.write_bytes(data)
