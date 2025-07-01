import textwrap
import os.path
from telegramtui.src import npyscreen
from telegramtui.src.telegramApi import client
from PIL import Image
from telethon.tl import types

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

    def update_messages(self, current_user):
        messages = self.get_messages_info(current_user)

        color_data = []
        data = []
        for i in range(len(messages) - 1, -1, -1):
            # replace empty char
            if messages[i].message:
                messages[i].message = messages[i].message.replace(chr(8203), '')

            data.append(messages[i].name + " " + messages[i].message)
            color_data.append(messages[i].color)

        self.entry_widget.highlighting_arr_color_data = color_data

        self.values = data

        if len(messages) > self.height - 3:
            self.entry_widget.start_display_at = len(messages) - self.height + 3
        else:
            self.entry_widget.start_display_at = 0

        self.entry_widget.cursor_line = len(messages)

        self.name = client.dialogs[current_user].name
        self.footer = client.online[current_user]

        self.display()

    def get_messages_info(self, current_user):
        messages = client.get_messages(current_user)

        # get user info
        users, dialog_type, max_name_len = self.get_user_info(messages, current_user)
        max_read_mess = client.dialogs[current_user].read_outbox_max_id

        out = []
        for i in range(len(messages)):
            date = messages[i].date
            mess_id = messages[i].id

            if self.emoji:
                read = "⚫ " if max_read_mess < mess_id and messages[i].out else "  "
            else:
                read = "* " if max_read_mess < mess_id and messages[i].out else "  "

            # get name if message is forwarding
            prepare_forward_message = self.prepare_forward_messages(messages[i])

            # if dialog with user or bot
            if dialog_type == 1:
                # Use sender_id to get sender information
                sender_id = messages[i].sender_id
                if hasattr(sender_id, 'user_id'):
                    user_id = sender_id.user_id
                    if user_id in users:
                        user_name = users[user_id].name
                    else:
                        # Fallback to current dialog name
                        user_name = client.dialogs[current_user].name
                else:
                    user_name = "Unknown"
                
                user_name = user_name if prepare_forward_message is False else prepare_forward_message
                if user_name:
                    user_name = textwrap.wrap(user_name, self.width // 5)[0]
                else:
                    user_name = "Deleted Account"
                    
                offset = " " * (max_name_len - len(user_name))
                name = read + user_name + ":" + offset
                
                # Determine color based on sender
                color = []
                if user_id == client.me.id:
                    color = [self.parent.theme_manager.findPair(self, 'NO_EDIT')] * len(name)
                else:
                    color = [self.parent.theme_manager.findPair(self, 'WARNING')] * len(name)

            # if chat group
            elif dialog_type == 2:
                # For groups, sender is always available
                if messages[i].sender:
                    sender = messages[i].sender
                    user_name = sender.first_name or sender.last_name or sender.title or "Unknown"
                else:
                    user_name = "Unknown"
                
                user_name = user_name if prepare_forward_message is False else prepare_forward_message
                user_name = textwrap.wrap(user_name, self.width // 5)[0]
                name = read + user_name + ": "
                color = [self.parent.theme_manager.findPair(self, 'WARNING')] * len(name)

            # if channel
            elif dialog_type == 3:
                user_name = client.dialogs[current_user].name
                user_name = user_name if prepare_forward_message is False else prepare_forward_message
                user_name = textwrap.wrap(user_name, self.width // 5)[0]
                name = user_name + ": "
                color = [self.parent.theme_manager.findPair(self, 'WARNING')] * len(name)

            else:
                name = ""
                color = [0]

            media = messages[i].media if hasattr(messages[i], 'media') else None
            mess = messages[i].message if hasattr(messages[i], 'message') \
                                          and isinstance(messages[i].message, str) else None

            image_name = ""
            if self.aalib and media is not None and hasattr(media, 'photo'):
                image_name = name
                name = len(name) * " "

            # add message to out []
            self.prepare_message(out, mess, name, read, mess_id, color, date)

            # add media to out []
            self.prepare_media(out, media, name, image_name, read, mess_id, color, date)

        # update buffer
        self.buff_messages[current_user] = out

        # return Message obj
        return out

    # get names, colors for names
    def get_user_info(self, messages, current_user):

        # structure for the dictionary
        class user_info:
            def __init__(self, color, name):
                self.color = color
                self.name = name

        users = {}
        max_name_len = 0
        entity = client.dialogs[current_user].entity

        # 1 - dialog with user
        if isinstance(entity, types.User):
            dialog_type = 1
            # set interlocutor
            name = entity.first_name or entity.last_name or entity.title or "Unknown"
            users[entity.id] = user_info(
                self.parent.theme_manager.findPair(self, 'WARNING'), name)

            # set me
            name = client.me.first_name or client.me.last_name or "Me"
            users[client.me.id] = user_info(
                self.parent.theme_manager.findPair(self, 'NO_EDIT'), name)

            max_name_len = max(len(users[entity.id].name),
                               len(users[client.me.id].name))

        # 2 - chat group
        elif isinstance(entity, (types.Chat, types.ChatForbidden)):
            dialog_type = 2
            # Collect all participants in the chat
            participants = {}
            for message in messages:
                if message.sender:
                    sender = message.sender
                    if not sender.id in participants:
                        participants[sender.id] = sender
            
            # Create user info for each participant
            for user_id, sender in participants.items():
                name = sender.first_name or sender.last_name or sender.title or "Unknown"
                users[user_id] = user_info(
                    self.parent.theme_manager.findPair(self, 'WARNING'), name)
                max_name_len = max(max_name_len, len(name))

            # set me
            name = client.me.first_name or client.me.last_name or "Me"
            users[client.me.id] = user_info(
                self.parent.theme_manager.findPair(self, 'NO_EDIT'), name)
            max_name_len = max(max_name_len, len(name))

        # 3 - channel
        elif isinstance(entity, (types.Channel, types.ChannelForbidden)):
            dialog_type = 3

        # -1 not define
        else:
            dialog_type = -1

        return users, dialog_type, max_name_len

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