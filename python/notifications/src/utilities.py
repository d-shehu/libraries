from dataclasses    import dataclass

@dataclass
class SupportContact:
    appName:    str
    appVersion: str
    email:      str
    phone:      str

@dataclass
class NotificationTemplate:
    subject:    str
    short:      str
    body:       str
    html:       str

