# Create a new file called notification_store.py
import json
import os
import threading
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

class NotificationStore:
    def __init__(self, file_path='/opt/marzban/notification_data.json'):
        self.file_path = file_path
        self.lock = threading.Lock()
        self.data = defaultdict(bool)
        self.load()
    
    def load(self):
        """Load notification data from file"""
        try:
            if os.path.exists(self.file_path):
                with open(self.file_path, 'r') as f:
                    loaded_data = json.load(f)
                    # Convert to defaultdict
                    self.data = defaultdict(bool)
                    for k, v in loaded_data.items():
                        self.data[k] = v
                logger.info(f"Loaded notification data for {len(self.data)} entries")
            else:
                logger.info("No notification data file found, starting with empty data")
        except Exception as e:
            logger.error(f"Error loading notification data: {e}")
    
    def save(self):
        """Save notification data to file"""
        try:
            with open(self.file_path, 'w') as f:
                # Convert defaultdict to regular dict for JSON serialization
                json.dump(dict(self.data), f)
        except Exception as e:
            logger.error(f"Error saving notification data: {e}")
    
    def is_notified(self, key):
        """Check if a notification has been sent"""
        with self.lock:
            return self.data[key]
    
    def set_notified(self, key, value=True):
        """Mark a notification as sent"""
        with self.lock:
            self.data[key] = value
            self.save()
    
    def reset_notification(self, key):
        """Reset a notification status"""
        with self.lock:
            self.data[key] = False
            self.save()

# Create a singleton instance
notification_store = NotificationStore()
