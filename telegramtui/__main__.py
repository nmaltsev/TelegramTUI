from telegramtui.src.ui import App
import asyncio
import threading

def main():
    # Create the application instance
    TelegramTUI = App()
    
    # Run the application
    TelegramTUI.run()

if __name__ == "__main__":
    main()