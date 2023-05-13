from websocket import create_connection
from typing import List, Optional
import time,string
import re
from html import unescape
import requests

def get_vms():
    r = requests.get('https://raw.githubusercontent.com/rretroo/scripts/main/vms.json')
    return r.json()

def needs_shift(key):
    a = key.isalpha() and key.isupper()
    b = key.isdigit() and key not in '1234567890'
    c = key in '!@#$%^&*()_+{}|:"<>?~'
    return a or b or c
def for_typing(text):
    """Replaces all special characters in a text to their non-modifier counterparts"""
    mapping = {
        "!": "1", "@": "2", "#": "3", "$": "4", "%": "5", "^": "6", "&": "7", "*": "8", 
        "(": "9", ")": "0", "_": "-", "+": "=", "{": "[", "}": "]", ":": ";", "\"": "'", 
        "<": ",", ">": ".", "?": "/"
    }
    #for char in string.ascii_uppercase:
    #    mapping["{}".format(char)] = "{}{}".format("'", char.lower())
    for char in string.digits:
        mapping["{}".format(char)] = "{}".format(char)
    for k in mapping:
        text = text.replace(k,mapping[k])
    return text

def guac_decode(string: str) -> Optional[List[str]]:
    """Implementation of guacamole decoder
    Example: guac_decode(\"4.chat,5.hello\") -> [\"chat\", \"hello\"]"""

    if not string:
        return []

    idx: int = 0
    distance: int
    result: List[str] = []
    chars: List[str] = list(string)

    while True:
        dist_str: str = ""

        while chars[idx].isdecimal():
            dist_str += chars[idx]
            idx = idx + 1

        if idx >= 1:
            idx -= 1

        if not dist_str.isdigit():
            return None

        distance = int(dist_str)
        idx += 1

        if chars[idx] != ".":
            return None

        idx += 1

        addition: str = ""
        for num in range(idx, idx + distance):
            addition += chars[num]

        result.append(addition)

        idx += distance
        if idx >= len(chars):
            return None

        if chars[idx] == ",":
            pass
        elif chars[idx] == ";":
            break
        else:
            return None

        idx += 1

    return result

def guac_encode(*args: str) -> str:
    """Implementation of guacamole encoder
    Example: guac_encode(\"chat\", \"hello\") -> \"4.chat,5.hello;\" """

    return f"{','.join(f'{len(arg)}.{arg}' for arg in args)};"

def vm_url(vmname):
    if type(vmname) == int:
        return f'wss://computernewb.com/collab-vm/vm{vmname}'
    vms = get_vms()
    for i in vms:
        if vms[i] == vmname:
            return i

def ps_url(url):
    return """powershell -NoProfile -ExecutionPolicy Bypass -Command "iex ((New-Object System.Net.WebClient).DownloadString('"""+url+"""'))" """[:-1]
def ps_url_args(url,args):
    return f'powershell -NoProfile -ExecutionPolicy Bypass -Command "{args} iex -Command ((New-Object System.Net.WebClient).DownloadString(\'{url}\'))"'

class UserRank:
    user = 0
    registered = 1
    admin = 2
    mod = 3

class Client:
    def __init__(self,url: str):
        self.url = url
        url_vm = url.split('/')[-1]
        if url_vm == 'vm0': url_vm = 'vm0b0t'
        self.url_vm = url_vm
        self.ws = create_connection(url,subprotocols=['guacamole'])
        self.events = {
            'on_update': [],
            'on_packet': [],
            'on_nop': [],
            'on_chat': [],
            'on_pre_chat': [],
            'on_connect': [],
            'on_add_user': [],
            'on_remove_user': [],
            'on_rename_user': [],
            'on_turn_change': [],
            'on_turn': [],
            'on_vote_start': [],
            'on_vote_user': [],
            'on_vote_change': [],
            'on_vote_end': [],
            'on_screen_update': [],
            'on_size_change': [],
        }
        self.users = {}
        self.name = None
        self.actual_name = ''
        self.chat_debounce = False
        self.connect_timestamp = None
        self.screen = None
        self.screen_enabled = False
        self.open = True
    def enable_screen(self):
        import PIL
        from PIL import Image
        import base64
        from io import BytesIO
        self.screen_enabled = True
        self.screen = Image.new('RGB',(1,1),(0,0,0))
    def send(self,op: list):
        op = [str(i) for i in op]
        cmd = guac_encode(*op)
        print(f'{self.url_vm} Sent: {cmd}')
        self.ws.send(cmd)
    def bind(self,event: str,func):
        if event in self.events:
            self.events[event].append(func)
        else:
            raise KeyError(f'Event {event} does not exist')
    def trigger(self,event: str,args: list):
        if event in self.events:
            for func in self.events[event]:
                func(*args)
        else:
            raise KeyError(f'Event {event} does not exist')
    def update(self):
        self.trigger('on_update',[])
        ws = self.ws
        data = ws.recv()
        op = guac_decode(data)
        self.trigger('on_packet',[op])
        if len(op) == 0:
            return
        if op[0] == 'nop':
            self.send(['nop'])
            self.trigger('on_nop',[op])
        if op[0] == 'connect':
            success = bool(int(op[1]))
            if success:
                turns = bool(int(op[2]))
                votes = bool(int(op[3]))
            else:
                turns = False
                votes = False
            self.trigger('on_connect',[success,turns,votes])
            self.connect_timestamp = time.time()
        if op[0] == 'chat':
            name = op[1]
            text = op[2]
            if self.chat_debounce:
                if self.connect_timestamp:
                    if time.time() - self.connect_timestamp < 0.5:
                        self.trigger('on_pre_chat',[name,text])
                        return
            text = unescape(text)
            self.trigger('on_chat',[name,text])
            if name == '':
                pat1 = '^(.+) has started a vote to reset the VM.$'
                pat2 = '^(.+) has voted yes.$'
                pat3 = '^(.+) has voted no.$'
                pat4 = 'The vote to reset the VM has lost.'
                pat5 = 'The vote to reset the VM has won.'
                ret = re.search(pat1,text)
                if ret:
                    user = ret.groups()[0]
                    self.trigger('on_vote_start',[user])
                    return
                ret = re.search(pat2,text)
                if ret:
                    user = ret.groups()[0]
                    self.trigger('on_vote_user',[user,True])
                    return
                ret = re.search(pat3,text)
                if ret:
                    user = ret.groups()[0]
                    self.trigger('on_vote_user',[user,False])
                    return
                if text == pat4:
                    self.trigger('on_vote_end',[False])
                    return
                if text == pat5:
                    self.trigger('on_vote_end',[True])
                    return
        if op[0] == 'vote':
            yv = 0
            nv = 0
            active = False
            if int(op[1]) == 1:
                active = True
                time_ms = int(op[2])
                yv = int(op[3])
                nv = int(op[4])
                self.trigger('on_vote_change',[active,yv,nv,time_ms])
        if op[0] == 'adduser':
            amt = int(op[1])
            i = 1
            for _ in range(amt):
                name = op[i+1]
                rank = int(op[i+2])
                self.users[name] = rank
                self.trigger('on_add_user',[name,rank])
                i += 2
        if op[0] == 'remuser':
            amt = int(op[1])
            i = 1
            for _ in range(amt):
                name = op[i+1]
                if name in self.users:
                    del self.users[name]
                self.trigger('on_remove_user',[name])
                i += 1
        if op[0] == 'rename':
            success = int(op[1])
            if success == 1:
                old = op[2]
                new = op[3]
                rank = int(op[4])
                if old in self.users:
                    del self.users[old]
                self.users[new] = rank
                self.trigger('on_rename_user',[old,new,rank])
                if old == self.actual_name:
                    self.actual_name = new
        if op[0] == 'turn':
            time_ms = int(op[1])
            amt = int(op[2])
            users = op[3:]
            self.trigger('on_turn_change',[users,time_ms])
            if len(users) > 0 and self.actual_name and users[0] == self.actual_name:
                self.trigger('on_turn',[op])
        if op[0] == 'size':
            if self.screen_enabled:
                from PIL import Image
                layer = int(op[1])
                w = int(op[2])
                h = int(op[3])
                if layer == 0:
                    if self.screen:
                        sc = self.screen.crop((0,0,w,h))
                        self.screen = Image.new('RGB',(w,h),(0,0,0))
                        self.screen.paste(sc,(0,0))
                    else:
                        self.screen = Image.new('RGB',(w,h),(0,0,0))
                    self.trigger('on_size_change',[w,h])
        if op[0] == 'png':
            if self.screen_enabled:
                x = int(op[3])
                y = int(op[4])
                data = op[5]
                from PIL import Image
                from io import BytesIO
                import base64
                sc = Image.open(BytesIO(base64.b64decode(data)))
                if self.screen:
                    self.screen.paste(sc,(x,y))
                    self.trigger('on_screen_update',[op])

    def connect(self,vmname: str=None):
        if vmname == None:
            vmname = self.url_vm
        self.actual_name = self.name
        self.send(['connect',vmname])
    def close(self):
        self.open = False
        self.ws.close()
    def disconnect(self):
        self.send(['disconnect'])
    def rename(self,name: str):
        self.send(['rename',name])
        self.name = name
    def chat(self,text: str):
        self.send(['chat',text])
    def chat_long(self,text: str,limit: int=150,delay: float=0.15):
        c = [text[i:i+limit] for i in range(0,len(text),limit)]
        for i in c:
            self.chat(i)
            time.sleep(delay)
    def reply(self,name: str,text: str):
        self.chat(f'@{name} {text}')
    def turn(self,on: bool):
        self.send(['turn',int(on)])
    def admin(self,rank: int,admin_password: str):
        self.send(['admin',rank,admin_password])
    def key(self,key: int,down: bool):
        self.send(['key',key,int(down)])
    def press(self,key: int):
        self.key(key,True)
        self.key(key,False)
    def type(self,text: str,delay: float=0.01):
        for c in text:
            if needs_shift(c):
                self.key(65505,True)
            self.press(ord(c))
            if needs_shift(c):
                self.key(65505,False)
            time.sleep(delay)
    def unstick(self):
        keys = [65507,65513,65505,65509,65027,65508,65506,65407]
        for k in keys:
            self.press(k)
            self.press(k)
    def ctrl_alt_del(self):
        self.key(65507,True)
        self.key(65513,True)
        self.key(65535,True)
        self.key(65507,False)
        self.key(65513,False)
        self.key(65535,False)
    def alt_f4(self):
        self.key(65513,True)
        self.press(65473)
        self.key(65513,False)
    def win_r(self):
        k = 65515
        self.key(k,True)
        self.press(114)
        self.key(k,False)
    def win_key(self,key):
        k = 65515
        self.key(k,True)
        self.press(key)
        self.key(k,False)
    def ctrl_shift_esc(self):
        self.key(65507,True)
        self.key(65503,True)
        self.key(65307,True)
        time.sleep(0.1)
        self.key(65507,False)
        self.key(65503,False)
        self.key(65307,False)
    def cmdline(self,cmd: str):
        self.win_r()
        time.sleep(2.5)
        self.type(cmd,delay=0.015)
        self.press(65293)
    def mainloop(self):
        while self.open:
            self.update()
            time.sleep(0)