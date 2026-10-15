import urllib.request
import urllib.parse
import logging
from typing import Optional
from backend.app.config import settings

logger = logging.getLogger("yt_summarizer")

class WhatsAppService:
    """
    Direct background WhatsApp delivery service.
    Automates sending the message directly into WhatsApp Web and pressing
    Enter automatically, so it is delivered without manual clicking.
    """

    @classmethod
    def send_summary_direct(
        cls,
        phone: str,
        video_title: str,
        channel_name: str,
        video_url: str,
        one_sentence_takeaway: str,
        key_takeaways: list,
        action_items: list = None,
        published_at: Optional[Any] = None,
        apikey: Optional[str] = None
    ) -> bool:
        """
        Sends the clean summary directly to WhatsApp with video publishing day and date.
        """
        from datetime import datetime

        # Ensure proper Pakistani international format (+923155619203)
        clean_phone = phone.replace(" ", "").replace("-", "")
        if clean_phone.startswith("03") and len(clean_phone) == 11:
            clean_phone = "+92" + clean_phone[1:]
        elif not clean_phone.startswith("+"):
            clean_phone = "+" + clean_phone

        # Format Published Day & Date in Pakistan Standard Time (Asia/Karachi / Islamabad)
        date_str = ""
        if published_at:
            from zoneinfo import ZoneInfo
            from datetime import timezone
            pkt_tz = ZoneInfo("Asia/Karachi")

            dt_utc = None
            if isinstance(published_at, str):
                try:
                    dt_utc = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                except Exception:
                    pass
            elif isinstance(published_at, datetime):
                dt_utc = published_at

            if dt_utc:
                if dt_utc.tzinfo is None:
                    # Stored SQLite UTC datetimes are naive
                    dt_utc = dt_utc.replace(tzinfo=timezone.utc)
                pkt_time = dt_utc.astimezone(pkt_tz)
                date_str = pkt_time.strftime("%A, %d %b %Y (%I:%M %p PKT)")
            else:
                date_str = str(published_at)[:19]

        # Format clean bullet points
        bullets = ""
        if key_takeaways:
            bullets = "\n".join([f"• {k}" for k in key_takeaways[:5]])

        actions = ""
        if action_items:
            actions = "\n\n💡 *Action Steps:*\n" + "\n".join([f"→ {a}" for a in action_items[:3]])

        date_line = f"📅 *Published:* {date_str}\n" if date_str else ""

        message = (
            f"🎬 *{video_title}*\n"
            f"👤 *Channel:* {channel_name}\n"
            f"{date_line}"
            f"🔗 *Watch Video:* {video_url}\n\n"
            f"📌 *Main Takeaway:*\n"
            f"{one_sentence_takeaway}\n\n"
            f"📝 *Key Points:*\n"
            f"{bullets}{actions}\n\n"
            f"✨ _YouTube Sub Summarizer_"
        )

        # 1. First priority: Twilio Cloud WhatsApp API (100% direct inbox delivery, 0 clicks, no browser needed)
        account_sid = getattr(settings, "TWILIO_ACCOUNT_SID", "")
        auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", "")
        twilio_phone = getattr(settings, "TWILIO_WHATSAPP_NUMBER", "+14155238886")

        if account_sid and auth_token:
            try:
                from twilio.rest import Client
                client = Client(account_sid, auth_token)
                from_num = f"whatsapp:{twilio_phone}" if not twilio_phone.startswith("whatsapp:") else twilio_phone
                to_num = f"whatsapp:{clean_phone}" if not clean_phone.startswith("whatsapp:") else clean_phone
                
                logger.info(f"[WhatsApp] Dispatching summary directly via Twilio Cloud to {to_num}...")
                resp = client.messages.create(
                    from_=from_num,
                    to=to_num,
                    body=message
                )
                logger.info(f"[WhatsApp] Successfully delivered to WhatsApp inbox! SID: {resp.sid}")
                return True
            except Exception as e:
                logger.error(f"[WhatsApp] Twilio direct delivery encountered: {str(e)}")

        # 2. Local browser automation fallback
        try:
            import pywhatkit
            logger.info(f"[WhatsApp] Triggering automated delivery to {clean_phone} via pywhatkit...")
            pywhatkit.sendwhatmsg_instantly(
                phone_no=clean_phone,
                message=message,
                wait_time=8,
                tab_close=False,
                close_time=3
            )
            return True
        except Exception as e:
            logger.warning(f"[WhatsApp] Browser dispatch encountered: {str(e)}")

        return False
