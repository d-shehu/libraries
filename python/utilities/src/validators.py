import re

class Validator:
    ValidEmailRegex = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,7}"

    @staticmethod
    def IsValidEmailAddress(emailAddressStr: str) -> bool:
        return re.fullmatch(Validator.ValidEmailRegex, emailAddressStr) is not None

    @staticmethod
    def IsValidEmailList(emailListStr: str, allowEmpty: bool = False) -> bool:
        success = False

        try:
            if emailListStr != "":
                lsEmails = emailListStr.split(",")

                invalidEmail = False
                for email in lsEmails:
                    if not Validator.IsValidEmailAddress(email):
                        invalidEmail = True
                        break

                success = not invalidEmail
            else:
                success = allowEmpty
        finally:
            return success
            
