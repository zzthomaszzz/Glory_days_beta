from shared.items import ITEMS


def handle_purchase(player, item_key, shops):
    if item_key not in ITEMS:
        return
    item = ITEMS[item_key]
    near = any(
        (player.x - (s.x + s.SIZE // 2)) ** 2 + (player.y - (s.y + s.SIZE // 2)) ** 2 <= s.RANGE ** 2
        for s in shops.values()
    )
    if not near:
        return
    if player.gold < item["cost"]:
        return
    empty = next((i for i, slot in enumerate(player.inventory) if slot is None and i < 3), None)
    if empty is None:
        return
    player.gold -= item["cost"]
    player.inventory[empty] = item_key
    for stat, val in item["stats"].items():
        setattr(player, stat, getattr(player, stat, 0) + val)


def handle_sell(player, slot):
    if not (0 <= slot < 3):
        return
    item_key = player.inventory[slot]
    if item_key not in ITEMS:
        return
    item = ITEMS[item_key]
    player.inventory[slot] = None
    player.gold += item["cost"] // 2
    for stat, val in item["stats"].items():
        setattr(player, stat, getattr(player, stat, 0) - val)
