from django import template

register = template.Library()

def callmethod(obj, methodname):
    method = getattr(obj, methodname)
    if "__callArg" in obj.__dict__:
        ret = method(*obj.__callArg)
        del obj.__callArg
        return ret
    return method()


def args(obj, arg):
    if not "__callArg" in obj.__dict__:
        obj.__callArg = []
    obj.__callArg.append(arg)
    return obj
    

def get_photo_user(user):
        if user.socialaccount_set.exists():
            social_account = user.socialaccount_set.first()
            return social_account.get_avatar_url()
        else:
            return None
        
def get_first_name(user):
    if user.first_name == "":
        return user.username
    return user.first_name

def number_to_price(number):
    return str(number).replace(",", ".")

register.filter("call", callmethod)
register.filter("args", args)
register.filter("get_photo_user", get_photo_user)
register.filter("get_first_name", get_first_name)
register.filter("number_to_price", number_to_price)