import curses
import os
import asyncio
from telegramtui.src.telegramApi import client
from telegramtui.src import npyscreen

class SendFileForm(npyscreen.ActionForm):

    def create(self):
        self.name = "Upload File (Press TAB)"
        new_handlers = {
            # exit
            "^Q": self.exit_func,
            155: self.exit_func,
            curses.ascii.ESC: self.exit_func
        }
        self.add_handlers(new_handlers)

        self.filename = self.add(npyscreen.TitleFilename, name="Filename:")
        self.status = self.add(npyscreen.Textfield, name="Status:", editable=False)

    def on_ok(self):
        self.status.value = ""
        self.display()

        if os.path.isfile(self.filename.value):
            current_user = self.parentApp.MainForm.chatBoxObj.value
            
            # Schedule file send in async thread
            asyncio.run_coroutine_threadsafe(
                self.send_file_async(current_user, self.filename.value),
                client.loop
            )
            
            # Optimistically update UI
            self.parentApp.MainForm.messageBoxObj.update_messages(current_user)
            self.parentApp.switchForm("MAIN")
        else:
            self.status.value = "File is not exist"
            self.display()

    async def send_file_async(self, user_id, file_path):
        """Asynchronously send a file with progress updates"""
        try:
            # Create progress callback that updates UI
            def progress_callback(sent_bytes, total):
                # Schedule UI update in main thread
                self.parentApp.queue_event(npyscreen.Event("event_update_progress", 
                                                          sent_bytes=sent_bytes, 
                                                          total=total))
            
            # Send the file using async method
            await client.file_send(file_path, user_id, progress_callback)
            
            # Update messages after successful send
            self.parentApp.queue_event(npyscreen.Event("event_update_messages", user_id=user_id))
            
        except Exception as e:
            # Handle errors (could show a notification in real app)
            print(f"Error sending file: {e}")

    def event_update_progress(self, event):
        """Handle progress update events in main thread"""
        name = "Status: "
        status = (event.sent_bytes * (self.max_x - len(name) - 8)) // event.total
        status = 1 if status == 0 else status
        self.status.value = name + "-" * status + ">"
        self.display()

    def event_update_messages(self, event):
        """Update messages after successful file send"""
        self.parentApp.MainForm.messageBoxObj.update_messages(event.user_id)
        self.parentApp.MainForm.messageBoxObj.display()

    def on_cancel(self):
        self.status.value = ""
        self.parentApp.switchForm("MAIN")

    def exit_func(self, _input):
        exit(0)