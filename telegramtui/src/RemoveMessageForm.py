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

        self.add_handlers({
            "^Q": self.exit_func,
            155: self.exit_func,
            curses.ascii.ESC: self.exit_func
        })

        self.display()

    def on_ok(self):
        asyncio.ensure_future(self._delete_selected_message())

    async def _delete_selected_message(self):
        current_message = self.parentApp.MainForm.messageBoxObj.entry_widget.cursor_line
        current_user = self.parentApp.MainForm.chatBoxObj.value
        messages = await client.get_messages(current_user)

        try:
            selected_message = messages[len(messages) - current_message - 1]
            await client.delete_message(current_user, selected_message.id)

            # Update local cache
            client.messages[current_user] = [
                msg for msg in client.messages[current_user] if msg.id != selected_message.id
            ]
            self.parentApp.MainForm.messageBoxObj.update_messages(current_user)
            self.parentApp.MainForm.messageBoxObj.display()
            self.parentApp.switchForm("MAIN")
        except IndexError:
            npyscreen.notify_confirm("Invalid message selection.", title="Error")

    def on_cancel(self):
        self.parentApp.switchForm("MAIN")

    def exit_func(self, _input):
        exit(0)
