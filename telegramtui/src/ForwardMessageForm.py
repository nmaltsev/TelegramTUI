import curses
import asyncio
from telegramtui.src.telegramApi import client
from telegramtui.src import npyscreen
from telethon.tl import types

class ForwardMessage(npyscreen.BoxTitle):

    def create(self):
        data = []
        for i in range(len(client.dialogs)):
            data.append(client.dialogs[i].name)

        self.values = data

    def when_value_edited(self):
        if self.value is not None:
            # Get the current message and user
            current_message = self.parent.parentApp.MainForm.messageBoxObj.entry_widget.cursor_line
            current_user = self.parent.parentApp.MainForm.chatBoxObj.value
            messages = self.parent.parentApp.MainForm.messageBoxObj.get_messages_info(current_user)

            # The message to forward
            message_id = messages[-current_message - 1].id
            
            # Get the source and target entities
            from_entity = client.dialogs[current_user].entity
            to_entity = client.dialogs[self.value].entity

            # Schedule the forwarding in the async loop
            loop = client.loop
            asyncio.run_coroutine_threadsafe(
                self.forward_message(from_entity, to_entity, message_id),
                loop
            )

            # Switch back to the main form
            self.parent.parentApp.switchForm("MAIN")

    async def forward_message(self, from_entity, to_entity, message_id):
        """Asynchronously forward a message"""
        try:
            # Forward the message
            await client.client.forward_messages(
                to_entity,
                [message_id],
                from_entity
            )
            
            # Update the target dialog
            target_index = self.value
            if client.messages[target_index] is None:
                await client.get_messages(target_index)
            
            # Add the forwarded message to local cache
            new_message = await client.client.get_messages(
                to_entity,
                limit=1
            )
            if new_message:
                client.messages[target_index].insert(0, new_message[0])
                client.messages[target_index].sort(key=lambda x: x.id, reverse=True)
                client.remove_duplicates(client.messages[target_index])
                
                # Trigger UI update
                client.need_update_message = 1
                client.need_update_current_user = target_index

        except Exception as e:
            # Handle errors (could show a notification in real app)
            print(f"Error forwarding message: {e}")


class ForwardMessageForm(npyscreen.ActionForm):

    def create(self):
        self.name = "Forward Message"
        new_handlers = {
            # exit
            "^Q": self.exit_func,
            155: self.exit_func,
            curses.ascii.ESC: self.exit_func
        }
        self.add_handlers(new_handlers)

        fwd = self.add(ForwardMessage, name="Select User")
        fwd.create()

    def on_ok(self):
        self.parentApp.switchForm("MAIN")

    def on_cancel(self):
        self.parentApp.switchForm("MAIN")

    def exit_func(self, _input):
        exit(0)