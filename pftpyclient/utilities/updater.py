import shutil
import stat
import subprocess
import wx
import time
import sys
import os
import platform
import traceback
from pathlib import Path
from loguru import logger
from typing import Optional, Dict
from pftpyclient.wallet_ux.dialog_parent import WalletDialogParent

REPO_URL = "https://github.com/postfiatorg/pftpyclient"

def get_commit_details(branch: str) -> Optional[Dict[str, str]]:
    """Fetch detailed information about the latest remote commit"""
    try:
        # Fetch the latest changes
        subprocess.run(['git', 'fetch'], check=True)

        # Get the commit message and details
        result = subprocess.run(
            ['git', 'log', '-1', f'origin/{branch}', '--pretty=format:%h%n%an%n%ad%n%s%n%b'],
            capture_output=True,
            text=True,
            check=True
        )

        # Parse the output
        lines = result.stdout.strip().split('\n')
        if len(lines) >= 4:
            return {
                'hash': lines[0],
                'author': lines[1],
                'date': lines[2],
                'subject': lines[3],
                'body': '\n'.join(lines[4:]) if len(lines) > 4 else ''
            }
        return None
    except subprocess.CalledProcessError:
        return None

class UpdateDialog(wx.Dialog):
    def __init__(self, parent: WalletDialogParent, commit_details: Dict[str, str], branch: str):
        super().__init__(parent, title="Update Available", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.commit_details = commit_details
        self.branch = branch
        self.setup_ui()
        self.Center()

    def setup_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        version_tag = 'dev ' if self.branch == 'dev' else ''

        # Create HTML content
        html_content = f"""
        <html>
        <body>
        <h3>A new {version_tag}version of PftPyClient is available</h3>
        <p>Latest update details:</p>
        <pre>
Commit: {self.commit_details['hash']}
Author: {self.commit_details['author']}
Date: {self.commit_details['date']}

{self.commit_details['subject']}

{self.commit_details['body']}
        </pre>
        <p>Would you like to update now?</p>
        </body>
        </html>
        """

        # HTML window for content
        self.html_window = wx.html.HtmlWindow(
            self,
            style=wx.html.HW_SCROLLBAR_AUTO,
            size=(500, 300)
        )
        self.html_window.SetPage(html_content)
        main_sizer.Add(self.html_window, 1, wx.EXPAND | wx.ALL, 10)

        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        update_btn = wx.Button(self, wx.ID_YES, "Update Now")
        update_btn.Bind(wx.EVT_BUTTON, self.on_update)
        skip_btn = wx.Button(self, wx.ID_NO, "Skip")
        skip_btn.Bind(wx.EVT_BUTTON, self.on_skip)
        
        btn_sizer.Add(update_btn, 0, wx.ALL, 5)
        btn_sizer.Add(skip_btn, 0, wx.ALL, 5)
        main_sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 5)

        self.SetSizer(main_sizer)
        main_sizer.Fit(self)

    def on_update(self, event):
        """Handle update button click"""
        self.EndModal(wx.ID_YES)

    def on_skip(self, event):
        """Handle skip button click"""
        self.EndModal(wx.ID_NO)

    def on_close(self, event):
        """Handle window close button (X)"""
        self.EndModal(wx.ID_NO)

def remove_with_retry(path: Path) -> bool:
    """Remove a file or directory with retries and permission fixes"""
    if not path.exists():
        return True

    try:
        if path.is_file():
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # Restrict permissions
            path.unlink(missing_ok=True)
        elif path.is_dir():
            # Make all files and directories writable
            for root, dirs, files in os.walk(path):
                for d in dirs:
                    try:
                        os.chmod(Path(root) / d, stat.S_IRWXU)  # 0o700
                    except Exception:
                        pass
                for f in files:
                    try:
                        os.chmod(Path(root) / f, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
                    except Exception:
                        pass
            
            # Attempt removal
            shutil.rmtree(path, onerror=handle_remove_error)

        return not path.exists()
    except Exception as e:
        print(f"Failed to remove {path}: {e}")
        return False

def handle_remove_error(func, path, excinfo):
    """Error handler for shutil.rmtree that handles readonly files"""
    try:
        os.chmod(path, stat.S_IRWXU)  # Restrict permissions
        func(path)  # Try again
    except Exception as e:
        print(f"Error handling removal of {path}: {e}")
