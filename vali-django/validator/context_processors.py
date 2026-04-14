from django.conf import settings


def validator_identity(request):
    """Expose validator identity to all templates."""
    name = getattr(settings, "VALIDATOR_DISPLAY_NAME", "")
    hotkey = getattr(settings, "VALIDATOR_HOTKEY", "")
    wallet = getattr(settings, "VALIDATOR_WALLET", "")
    return {
        "validator_display_name": name,
        "validator_hotkey_name": hotkey,
        "validator_wallet_name": wallet,
    }
