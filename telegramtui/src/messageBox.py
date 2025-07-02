import textwrap
import os.path
from telegramtui.src import npyscreen
from telegramtui.src.telegramApi import client
from PIL import Image
from telethon.tl import types
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument, MessageMediaWebPage
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument, MessageMediaWebPage
from telethon.tl.types import UserStatusOffline, UserStatusOnline
from telethon.tl.types import MessageMediaUnsupported
import aalib

class MessageBox(npyscreen.BoxTitle):

    def create(self, **kwargs):
        self.emoji = kwargs['emoji'] if 'emoji' in kwargs else False
        self.aalib = kwargs['aalib'] if 'aalib' in kwargs else False

        self.buff_messages = len(client.dialogs) * [None]

    def when_value_edited(self):
        if self.value is not None:
            self.parent.parentApp.getForm("MESSAGE_INFO").update()
            self.parent.parentApp.switchForm("MESSAGE_INFO")

    def when_cursor_moved(self):
        self.parent.parentApp.queue_event(npyscreen.Event("event_messagebox_change_cursor"))

    _contained_widget = npyscreen.Pager

    def update_messages(self, current_user):
        # Call async get_messages_info safely and wait for result
        messages_info = client.run_async_task(self.get_messages_info(current_user)).result()
        self.values = messages_info
        self.display()

    async def get_messages_info(self, current_user):
        if not client.dialogs or current_user >= len(client.dialogs):
            return ["No dialogs loaded"]

        entity = client.dialogs[current_user].entity
        messages = await client.get_messages(current_user)
        if not messages:
            return ["No messages"]

        lines = []
        for message in messages:
            sender_name, color = self.get_user_info(message)
            text = message.message or ""

            # Prepare message display (wrap text etc.)
            formatted = self.prepare_message(sender_name, text, color)
            lines.extend(formatted)

            # Forwarded message info
            if message.fwd_from:
                fwd_lines = self.prepare_forward_messages(message)
                lines.extend(fwd_lines)

            # Show media preview for photos/stickers
            if message.media:
                media_lines = self.prepare_media(message.media)
                if media_lines:
                    lines.extend(media_lines)

            # Divider between messages
            lines.append("")

        return lines

    def prepare_message(self, sender, text, color):
        wrapped_text = textwrap.wrap(text, width=self.width - 10)
        lines = [f"{sender}: " + wrapped_text[0] if wrapped_text else f"{sender}: "]
        for line in wrapped_text[1:]:
            lines.append(" " * (len(sender) + 2) + line)
        # You can add color codes here if needed, npyscreen supports colors via attr
        return lines

    def prepare_forward_messages(self, message):
        fwd = message.fwd_from
        fwd_str = "Forwarded"
        if fwd.from_name:
            fwd_str += f" from {fwd.from_name}"
        return [f"  {fwd_str}"]

    def prepare_media(self, media):
        # Only handle photo media for now
        if isinstance(media, MessageMediaPhoto):
            try:
                file_path = client.run_async_task(client.download_media(media, None)).result()
                if not file_path:
                    return ["[Image: Download failed]"]

                # Load image, convert to ASCII art with aalib
                with Image.open(file_path) as img:
                    img = img.convert("L").resize((40, 20))  # resize for ASCII
                    screen = aalib.AsciiScreen(width=40, height=20)
                    screen.put_image(0, 0, img)
                    ascii_art = screen.render()
                return ascii_art.splitlines()
            except Exception as e:
                return [f"[Image load error: {str(e)}]"]

        # Add support for other media types as needed
        return []

    def get_user_info(self, message):
        # Return sender name and a dummy color name (npyscreen color pair)
        sender = None
        color = 'DEFAULT'

        if message.sender:
            sender = message.sender.first_name or "Unknown"
            if message.sender.id == client.me.id:
                color = 'GOOD'
            else:
                color = 'NO_EDIT'

        else:
            sender = "Unknown"

        return sender, color
    # set forwarding name if need
    def prepare_forward_messages(self, message):
        user_name = False
        fwd_from = message.fwd_from if hasattr(message, 'fwd_from') else None
        if fwd_from is not None:
            return "Fwd"  # Simplified for UI performance
        
        return user_name

    # structure for out message
    class Messages:
        def __init__(self, name, date, color, message, id, read):
            self.name = name
            self.date = date
            self.color = color
            self.message = message
            self.id = id
            self.read = read

    # add message to Message structure
    def prepare_message(self, out, mess, name, read, mess_id, color, date):

        # add message to return
        if mess is not None and mess != "":
            if mess.find("\n") == -1:
                if len(mess) + len(name) + len(read) > self.width - 10:
                    max_char = self.width - len(name) - 10
                    arr = textwrap.wrap(mess, max_char)

                    for k in range(len(arr) - 1, 0, -1):
                        out.append(self.Messages(len(name) * " ", date, color, arr[k], mess_id, read))

                    out.append(self.Messages(name, date, color, arr[0], mess_id, read))
                else:
                    out.append(self.Messages(name, date, color, mess, mess_id, read))
            # multiline message
            else:
                mess = mess.split("\n")
                for j in range(len(mess) - 1, 0, -1):
                    if len(mess[j]) + len(name) + len(read) > self.width - 10:
                        max_char = self.width - len(name) - 10
                        arr = textwrap.wrap(mess[j], max_char)

                        for k in range(len(arr) - 1, -1, -1):
                            out.append(self.Messages(len(name) * " ", date, color, arr[k], mess_id, read))
                    else:
                        out.append(self.Messages(len(name) * " ", date, color, mess[j], mess_id, read))

                if len(mess[0]) + len(name) + len(read) > self.width - 10:
                    max_char = self.width - len(name) - 10
                    arr = textwrap.wrap(mess[0], max_char)

                    for k in range(len(arr) - 1, 0, -1):
                        out.append(self.Messages(len(name) * " ", date, color, arr[k], mess_id, read))

                    out.append(self.Messages(name, date, color, arr[0], mess_id, read))
                else:
                    out.append(self.Messages(name, date, color, mess[0], mess_id, read))

    # add media to Message structure
    def prepare_media(self, out, media, name, image_name, read, mess_id, color, date):
        if media is not None:
            if hasattr(media, 'photo') and self.aalib:
                import aalib
                try:
                    if not os.path.isfile(os.getcwd() + "/downloads/" + str(media.photo.id) + ".jpg"):
                        # download picture
                        client.download_media(media, "downloads/" + str(media.photo.id))

                    max_width = int((self.width - len(image_name) - 11) / 1.3)
                    max_height = int((self.height - 12) / 1.3)

                    screen = aalib.AsciiScreen(width=max_width, height=max_height)
                    image = Image.open(os.getcwd() + "/downloads/" + str(media.photo.id) + ".jpg").convert('L').resize(
                        screen.virtual_size)
                    screen.put_image((0, 0), image)
                    image_text = screen.render()

                    image_text = image_text.split("\n")
                    for k in range(len(image_text) - 1, 0, -1):
                        out.append(self.Messages(len(image_name) * " ", date, color, image_text[k], mess_id, read))
                    out.append(self.Messages(image_name, date, color, image_text[0], mess_id, read))
                except:
                    out.append(self.Messages(image_name, date, color, "<Unknown photo>", mess_id, read))

            elif hasattr(media, 'photo') and not self.aalib:
                out.append(self.Messages(name, date, color, "<Image>", mess_id, read))

            elif hasattr(media, 'document'):
                try:
                    # print sticker like a emoji
                    for attr in media.document.attributes:
                        if isinstance(attr, types.DocumentAttributeSticker):
                            out.append(self.Messages(name, date, color,
                                                     "Sticker: " + attr.alt, mess_id, read))
                            break
                    else:
                        out.append(self.Messages(name, date, color, "<Document>", mess_id, read))
                except:
                    out.append(self.Messages(name, date, color, "<Document>", mess_id, read))