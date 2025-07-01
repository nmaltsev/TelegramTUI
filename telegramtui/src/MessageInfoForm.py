import curses
import asyncio
import logging
from telegramtui.src.telegramApi import client
from telegramtui.src import npyscreen
import textwrap
from datetime import timedelta
from telegramtui.src.config import get_config
from telethon.tl import types

logging.basicConfig(filename="newfile.log",
                    format='%(asctime)s %(message)s',
                    filemode='w')
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


class MessageInfoForm(npyscreen.ActionForm):

    def create(self):
        self.name = "Message Info"
        new_handlers = {
            # exit
            "^Q": self.exit_func,
            155: self.exit_func,
            curses.ascii.ESC: self.exit_func
        }
        self.add_handlers(new_handlers)

        config = get_config()
        self.timezone = int(config.get('other', 'timezone'))

        self.mess_id = self.add(npyscreen.TitleText, name="Message id:", editable=False)
        self.date = self.add(npyscreen.TitleText, name="Date:      ", editable=False)
        self.sender = self.add(npyscreen.TitleText, name="Sender:    ", editable=False)
        self.forward = self.add(npyscreen.TitleText, name="Fwd from:  ", editable=False)
        self.attachment = self.add(npyscreen.TitleText, name="Attachment:", editable=False)
        self.text = self.add(npyscreen.TitleMultiLine, name="Text:      ", max_height=5, scroll_exit=True)

    def update(self):
        current_user = self.parentApp.MainForm.chatBoxObj.value
        current_message = self.parentApp.MainForm.messageBoxObj.value
        messages = self.parentApp.MainForm.messageBoxObj.get_messages_info(current_user)
        current_id = messages[-current_message - 1].id

        message_info = client.get_message_by_id(current_user, current_id)
        prepared_text = self.prepare_message(message_info.message)

        self.current_user = current_user
        self.mess_id.value = current_id
        self.date.value = str(messages[-current_message - 1].date + (timedelta(self.timezone) // 24))
        self.attachment.value = self.prepare_media(message_info)
        self.forward.value = self.prepare_forward_messages(message_info)
        self.text.values = prepared_text
        self.text.max_height = len(prepared_text)
        
        # Update sender information asynchronously
        asyncio.run_coroutine_threadsafe(
            self.update_sender(message_info),
            client.loop
        )

    async def update_sender(self, message):
        """Asynchronously update sender information"""
        try:
            if message.sender_id:
                # Get the sender entity
                sender = await client.client.get_entity(message.sender_id)
                
                # Format sender name based on type
                if isinstance(sender, types.User):
                    name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()
                    self.sender.value = f"{name} (id {sender.id})"
                elif isinstance(sender, types.Channel):
                    self.sender.value = f"{sender.title} (id {sender.id})"
                elif isinstance(sender, types.Chat):
                    self.sender.value = f"{sender.title} (id {sender.id})"
                else:
                    self.sender.value = f"Unknown entity (id {message.sender_id})"
            else:
                self.sender.value = "Unknown sender"
                
            # Refresh the display
            self.display()
        except Exception as e:
            logger.error(f"Error getting sender: {e}")
            self.sender.value = "Error loading sender"
            self.display()

    def prepare_message(self, mess):
        y, x = self.useable_space()
        x -= 12
        out = []
        if mess is not None and mess != "":
            mess = mess.split("\n")
            for i in range(len(mess)):
                if len(mess[i]) > x - 10:
                    max_char = x - 10
                    arr = textwrap.wrap(mess[i], max_char)
                    for j in range(len(arr)):
                        out.append(arr[j])
                else:
                    out.append(mess[i])
        return out

    def prepare_media(self, obj):
        media = obj.media if hasattr(obj, 'media') else None
        if media is not None:
            if hasattr(media, 'photo'):
                out = "photo"
            elif hasattr(media, 'document'):
                # Check for sticker attribute
                for attr in media.document.attributes:
                    if isinstance(attr, types.DocumentAttributeSticker):
                        out = "Sticker"
                        break
                else:
                    out = "Document"
            else:
                out = "Unknown attachment"
        else:
            out = "None"

        return out

    def prepare_forward_messages(self, message):
        fwd_from = message.fwd_from if hasattr(message, 'fwd_from') else None
        if fwd_from is None:
            return "None"
            
        try:
            # Handle saved messages
            if fwd_from.saved_from_peer:
                if isinstance(fwd_from.saved_from_peer, types.PeerUser):
                    return f"Saved from User (id {fwd_from.saved_from_peer.user_id})"
                elif isinstance(fwd_from.saved_from_peer, types.PeerChat):
                    return f"Saved from Chat (id {fwd_from.saved_from_peer.chat_id})"
                elif isinstance(fwd_from.saved_from_peer, types.PeerChannel):
                    return f"Saved from Channel (id {fwd_from.saved_from_peer.channel_id})"
                    
            # Handle regular forwards
            if fwd_from.from_id:
                if isinstance(fwd_from.from_id, types.PeerUser):
                    return f"User (id {fwd_from.from_id.user_id})"
                elif isinstance(fwd_from.from_id, types.PeerChat):
                    return f"Chat (id {fwd_from.from_id.chat_id})"
                elif isinstance(fwd_from.from_id, types.PeerChannel):
                    return f"Channel (id {fwd_from.from_id.channel_id})"
                    
            # Handle channel forwards
            if fwd_from.channel_post is not None:
                return f"Channel Post (id {fwd_from.channel_post})"
                
            # Handle from_name as fallback
            if fwd_from.from_name:
                return fwd_from.from_name
                
            return "Unknown forward source"
            
        except Exception as e:
            logger.error(f"Error parsing forward: {e}")
            return "Error parsing forward"

    def on_ok(self):
        self.parentApp.switchForm("MAIN")

    def on_cancel(self):
        self.parentApp.switchForm("MAIN")

    def exit_func(self, _input):
        exit(0)