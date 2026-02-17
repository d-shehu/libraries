import textwrap

from dataclasses    import dataclass
from typing         import Dict

# This package
from .notification  import NotificationType
from .utilities     import SupportContact, NotificationTemplate

class NotificationRenderer:
    def __init__(self, 
                 supportContact: SupportContact):
        
        self._supportContact = supportContact
        
    def render(self, 
               type: NotificationType,
               recipient: str,
               summary: str,
               message: str
               ) -> NotificationTemplate:
        
        # Create a template for the given notification type
        template = NotificationRenderer.Templates[type]
        fields = {
            "recipient":        recipient,
            "summary":          summary,
            "message":          textwrap.dedent(message),
            "sender_name":      self._supportContact.email,
            "app":              self._supportContact.appName,
            "version":          self._supportContact.appVersion,
            "support_email":    self._supportContact.email,
            "contact_phone":    self._supportContact.phone
        }

        # Fill in fields
        filledIn = NotificationTemplate(
            template.subject.format(**fields),
            template.short.format(**fields),
            template.body.format(**fields),
            template.html.format(**fields)
        )

        return filledIn

# Template definitions
    Footer = """\

                -------------------------------------------------
                Sent by:     {sender_name}
                Application: {app}
                Version:     {version}
                Contact:     {support_email} | {contact_phone}
            """
    
    FooterHTML = """\
    
                <hr style="border:none; border-top:1px solid #ddd;" />
                    
                <footer style="font-size:.9em; color:#555;">
                    Sent by&nbsp;&nbsp;<b>{sender_name}</b><br/>
                    Application:&nbsp;<b>{app}</b><br/>
                    Version:&nbsp;<b>{version}</b><br/>
                    Contact:&nbsp;
                    <a href="mailto:{support_email}">{support_email}</a> |
                    {contact_phone}
                </footer>
                """

    Templates: Dict[ NotificationType, NotificationTemplate] = {
        # Info notification
        NotificationType.Info: NotificationTemplate(
            subject="[{app}] ℹ️ Info – {summary}",
            short="ℹ️ Info: {message}",
            body="""\
                Dear {recipient},

                Summary : {summary}

                {message}

                Thank you for your attention.
                """ + Footer,
            html="""\
                <html>
                    <body style="font-family:sans-serif; line-height:1.5;">
                    <h3 style="color:#17a2b8;">ℹ️ Info – {summary}</h3>

                    <p>
                        <strong>Summary:</strong> {summary}
                    </p>
                    <blockquote style="white-space:pre-wrap;">{message}</blockquote>
                """ + FooterHTML + 
                """\
                    </body>
                </html>
                """
        ),

        # Warning notification
        NotificationType.Warning: NotificationTemplate(
            subject="[{app}] ⚠️ Warning – {summary}",
            short="⚠️ Warning: {message}",
            body="""\
                Dear {recepient},

                [{type}]
                Summary : {summary}

                {message}

                This is a non‑critical warning. Please review at your convenience.
                """ + Footer,
            html="""\
                <html>
                    <body style="font-family:sans-serif; line-height:1.5;">
                    <h3 style="color:#ffc107;">⚠️ Warning – {summary}</h3>

                    <p>
                        <strong>Summary:</strong> {summary}
                    </p>
                    <blockquote style="white-space:pre-wrap; margin-left:1em;">
                        {message}
                    </blockquote>

                    <p>This is a non‑critical warning. Review at your convenience.</p>
                """ + FooterHTML + 
                """\
                    </body>
                </html>
                """
        ),

        # Error notification
        NotificationType.Error: NotificationTemplate(
            subject="[{app}] ❌ Error – {summary}",
            short="❌ Error: {message}",
            body="""\
                Attn {recepient},

                {message}

                Please review and take action as soon as possible.
                """ + Footer,
            html="""\
                <html>
                    <body style="font-family:sans-serif; line-height:1.5;">
                    <h3 style="color:#dc3545;">❌ Error – {summary}</h3>

                    <p>
                        <strong>Summary:</strong> {summary}
                    </p>
                    <blockquote style="white-space:pre-wrap; margin-left:1em;">
                        {message}
                    </blockquote>

                    <p><em>Please review and take action as soon as possible.</em></p>
                """ + FooterHTML + 
                """\
                    </body>
                </html>
                """
        ),

        # Error notification
        NotificationType.Critical: NotificationTemplate(
            subject="[{app}] 🚨 CRITICAL – {summary}",
            short="🚨 CRITICAL: {message}",
            body="""\
                Attn {recepient},

                {message}

                Please review and take immediate action!
                """ + Footer,
            html="""\
                <html>
                    <body style="font-family:sans-serif; line-height:1.5;">
                    <h3 style="color:#dc3545;">🚨 CRITICAL – {summary}</h3>

                    <p>
                        <strong>Summary:</strong> {summary}
                    </p>
                    <blockquote style="white-space:pre-wrap; margin-left:1em;">
                        {message}
                    </blockquote>

                    <p><em>Please review and take immediate action!</em></p>
                """ + FooterHTML + 
                """\
                    </body>
                </html>
                """
        ),
    }