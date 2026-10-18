import sys
import subprocess
from src.app.config import settings
from src.app.utils.logger import logger

class NotificationService:
    """
    Displays native Windows Desktop Toast and Balloon notifications.
    Operates asynchronously and non-blocking.
    """

    @classmethod
    def show_toast(cls, title: str, message: str):
        """Displays native Windows desktop notification."""
        if not settings.ENABLE_DESKTOP_NOTIFICATIONS or sys.platform != "win32":
            return

        clean_title = title.replace("'", " ").replace('"', ' ').strip()[:60]
        clean_msg = message.replace("'", " ").replace('"', ' ').strip()[:140]

        ps_cmd = (
            "[void] [System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms'); "
            f"$obj = New-Object System.Windows.Forms.NotifyIcon; "
            f"$obj.Icon = [System.Drawing.SystemIcons]::Information; "
            f"$obj.BalloonTipTitle = '{clean_title}'; "
            f"$obj.BalloonTipText = '{clean_msg}'; "
            f"$obj.Visible = $True; "
            f"$obj.ShowBalloonTip(4000); "
            f"Start-Sleep -Milliseconds 1500; "
            f"$obj.Dispose()"
        )

        try:
            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NO_WINDOW

            subprocess.Popen(
                ["powershell.exe", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_cmd],
                creationflags=creationflags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception as e:
            logger.debug(f"Could not send desktop notification: {e}")

    @classmethod
    def notify_video_summarized(cls, channel_name: str, video_title: str):
        cls.show_toast(
            title=f"New Summary: {channel_name}",
            message=video_title
        )

    @classmethod
    def notify_daily_digest(cls, count: int):
        cls.show_toast(
            title="☕ Daily YouTube Briefing Ready",
            message=f"Digested {count} new videos across your subscribed channels."
        )
