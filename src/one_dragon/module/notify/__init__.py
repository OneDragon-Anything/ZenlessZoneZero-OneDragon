def handle_notify(*args, **kwargs):
    # Lazy import onepush
    from one_dragon.module.notify.notify import handle_notify
    return handle_notify(*args, **kwargs)
