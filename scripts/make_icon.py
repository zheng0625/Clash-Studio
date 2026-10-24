from pathlib import Path
import struct

root = Path(__file__).resolve().parents[1]
icons = []
for size in (32, 64, 128):
    data = bytearray()
    for y in reversed(range(size)):
        for x in range(size):
            a, b = x/size, y/size
            white = any((a-u)**2+(b-v)**2 < .055**2 for u,v in ((.33,.30),(.33,.68),(.68,.32)))
            white |= .305 < a < .355 and .32 < b < .67
            white |= abs((a-.33)+(b-.67)) < .035 and .34 < a < .67 and .32 < b < .67
            r,g,blue = (255,255,255) if white else (112,86,211)
            data.extend((blue,g,r,255))
    mask = bytes(((size+31)//32)*4*size)
    dib = struct.pack('<IiiHHIIiiII',40,size,size*2,1,32,0,len(data),0,0,0,0)+data+mask
    icons.append((size,dib))
offset = 6+16*len(icons)
entries = bytearray()
for size,dib in icons:
    entries.extend(struct.pack('<BBBBHHII',size,size,0,0,1,32,len(dib),offset))
    offset += len(dib)
path=root/'src-tauri/icons/icon.ico'
path.parent.mkdir(parents=True,exist_ok=True)
path.write_bytes(struct.pack('<HHH',0,1,len(icons))+entries+b''.join(dib for _,dib in icons))
print(path)
