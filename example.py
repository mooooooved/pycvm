# too lazy to write documentation just look at the source code

from cvm import *

bot = Client(vm_url('vm0b0t'))

bot.chat_debounce = True # strongly recommended, enables the on_pre_chat event
# this is because the server mass sends previous chat history when you connect, enabling this routes those to on_pre_chat instead of on_chat so if you're making stuff like commands it doesn't go over the previous messages

# bot.enable_screen()
# ^ enables screen features (requires PIL/Pillow, base64, io.BytesIO)

def on_connect(success,turns_enabled,votes_enabled):
    bot.chat("hello world")
    # bot.disconnect()
    # bot.close()
bot.bind('on_connect',on_connect)

def on_chat(name,text):
    print(f'{name} said: {text}')
bot.bind('on_chat',on_chat)

bot.rename("hello world test")
bot.connect('vm0b0t')
bot.mainloop()
