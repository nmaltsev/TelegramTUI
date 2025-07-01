from telegramtui.src import npyscreen
from telegramtui.src.MainForm import MainForm
from telegramtui.src.ContactsForm import ContactsForm
from telegramtui.src.SendFileForm import SendFileForm
from telegramtui.src.MessageInfoForm import MessageInfoForm
from telegramtui.src.ForwardMessageForm import ForwardMessageForm
from telegramtui.src.RemoveMessageForm import RemoveMessageForm

class App(npyscreen.StandardApp):

    def onStart(self):
        # Add all forms with their appropriate configurations
        self.MainForm = self.addForm("MAIN", MainForm)
        self.ContactsForm = self.addForm("CONTACTS", ContactsForm)
        self.SendFileForm = self.addForm("SEND_FILE", SendFileForm, lines=15)
        self.MessageInfoForm = self.addForm("MESSAGE_INFO", MessageInfoForm)
        self.ForwardMessageForm = self.addForm("FORWARD_MESSAGE", ForwardMessageForm)
        self.RemoveMessageForm = self.addForm("REMOVE_MESSAGE", RemoveMessageForm, lines=5, columns=20)
        
        # Add event handlers for new events
        self.add_event_hander("event_update_progress", self.handle_update_progress)
        self.add_event_hander("event_update_messages", self.handle_update_messages)
        
    def handle_update_progress(self, event):
        """Handle progress update events from background threads"""
        # Forward progress events to the active form
        if self.activeForm == "SEND_FILE":
            self.getForm("SEND_FILE").event_update_progress(event)
            
    def handle_update_messages(self, event):
        """Handle message update events from background threads"""
        # Forward message update events to the main form
        self.getForm("MAIN").event_update_main_form(event)
        # Also update specific message box if needed
        self.MainForm.messageBoxObj.update_messages(event.user_id)
        self.MainForm.messageBoxObj.display()