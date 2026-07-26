import os
from send2trash import send2trash

class TrashService:
    """Handles safe moving of files to the Windows Recycle Bin."""
    
    @staticmethod
    def send_to_recycle_bin(filepath):
        """Move file to OS Recycle Bin safely."""
        if not os.path.exists(filepath):
            return False, "File does not exist"

        try:
            send2trash(filepath)
            return True, "File moved to Recycle Bin"
        except Exception as e:
            return False, f"Failed to send to Recycle Bin: {str(e)}"
