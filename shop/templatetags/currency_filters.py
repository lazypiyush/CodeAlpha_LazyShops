from django import template

register = template.Library()

@register.filter(name='rupees')
def rupees(value):
    """Convert value to rupees format"""
    try:
        return f"₹{float(value):,.2f}"
    except (ValueError, TypeError):
        return f"₹0.00"
