import curses
import asyncio
from telegramtui.src.telegramApi import client
from telegramtui.src import npyscreen

class RemoveMessageForm(npyscreen.ActionForm):

    def create(self):
        y, x = self.parentApp.MainForm.useable_space()
        self.show_atx = x // 2 - 10
        self.show_aty = y // 2 - 5

        self.name = "Delete Message?"
        new_handlers = {
            # exit
            "^Q": self.exit_func,
            155: self.exit_func,
            curses.ascii.ESC: self.exit_func
        }
        self.add_handlers(new_handlers)

        self.status = self.add(npyscreen.Textfield, value="Are you sure?", editable=False)
        self.display()

    def on_ok(self):
        current_message = self.parentApp.MainForm.messageBoxObj.entry_widget.cursor_line
        current_user = self.parentApp.MainForm.chatBoxObj.value
        messages = self.parentApp.MainForm.messageBoxObj.get_messages_info(current_user)
        message_id = messages[-current_message - 1].id

        # Schedule deletion in async thread
        asyncio.run_coroutine_threadsafe(
            self.delete_message(current_user, message_id),
            client.loop
        )

        # Optimistically remove from local cache
        self.remove_from_cache(current_user, message_id)
        
        # Update UI immediately
        self.parentApp.MainForm.messageBoxObj.update_messages(current_user)
        self.parentApp.switchForm("MAIN")

    async def delete_message(self, user_id, message_id):
        """Asynchronously delete a message"""
        try:
            # Delete using the async method
            await client.delete_message(user_id, message_id)
            
            # Update UI in main thread
            self.parentApp.queue_event(npyscreen.Event("event_update_main_form"))
        except Exception as e:
            # Handle errors (could show a notification in real app)
            print(f"Error deleting message: {e}")

    def remove_from_cache(self, user_id, message_id):
        """Remove message from local cache immediately"""
        if user_id < len(client.messages) and client.messages[user_id]:
            # Create a new list without the deleted message
            new_data = [msg for msg in client.messages[user_id] if msg.id != message_id]
            client.messages[user_id] = new_data

    def on_cancel(self):
        self.parentApp.switchForm("MAIN")

    def exit_func(self, _input):
        exit(0)