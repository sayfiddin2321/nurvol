from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def gallery_page_url(context, parameter, number, anchor):
    query = context["request"].GET.copy()
    query[parameter] = number
    return f"?{query.urlencode()}#{anchor}"
