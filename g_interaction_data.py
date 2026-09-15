"""Hot-reloaded inventory and narrative authoring. IDs are save-game stable."""
SLOT_COUNT = 8
LANGUAGE = "zh_hant"  # en, zh_hans, zh_hant
ITEMS = {
    "health": {"name": "health", "description": "health_description", "stack": 1},
    "ammo": {"name": "ammo", "description": "ammo_description", "stack": 60},
    "key": {"name": "key", "description": "key_description", "stack": 1},
}
TEXT = {
    "inventory_controls": {"en": "Arrows: select  E/Enter: use  Esc/Tab: close", "zh_hans": "方向键：选择  E/回车：使用  Esc/Tab：关闭", "zh_hant": "方向鍵：選擇  E/回車：使用  Esc/Tab：關閉"},
    "dialogue_controls": {"en": "E/Enter: continue   Left/Right: choice   Esc: cancel", "zh_hans": "E/回车：继续  左右键：选择  Esc：取消", "zh_hant": "E/回車：繼續  左右鍵：選擇  Esc：取消"},
    "health_description": {"en": "Restores health. Use from the inventory.", "zh_hans": "恢复生命值。可在物品栏中使用。", "zh_hant": "恢復生命值。可在物品欄中使用。"},
    "ammo_description": {"en": "Spare pistol rounds. Used automatically when reloading.", "zh_hans": "备用手枪弹药。装弹时自动使用。", "zh_hant": "備用手槍彈藥。裝彈時自動使用。"},
    "key_description": {"en": "An old brass key. Used automatically at its matching door.", "zh_hans": "一把旧黄铜钥匙。在对应的门前自动使用。", "zh_hant": "一把舊黃銅鑰匙。在對應的門前自動使用。"},
    "automatic_item": {"en": "This item is used automatically at the appropriate place.", "zh_hans": "这件物品会在适当的地方自动使用。", "zh_hant": "這件物品會在適當的地方自動使用。"},
    "healthy": {"en": "You are already in good health.", "zh_hans": "你的生命值已满。", "zh_hant": "你的生命值已滿。"},
    "healed": {"en": "You used the medicine.", "zh_hans": "你使用了药品。", "zh_hant": "你使用了藥品。"},
    "inventory": {"en": "Inventory", "zh_hans": "物品栏", "zh_hant": "物品欄"},
    "take": {"en": "Take this item?", "zh_hans": "拾取这件物品？", "zh_hant": "拾取這件物品？"},
    "yes": {"en": "Yes", "zh_hans": "是", "zh_hant": "是"},
    "no": {"en": "No", "zh_hans": "否", "zh_hant": "否"},
    "full": {"en": "There is not enough space in your inventory.", "zh_hans": "物品栏空间不足。", "zh_hant": "物品欄空間不足。"},
    "empty": {"en": "Empty", "zh_hans": "空", "zh_hant": "空"},
    "health": {"en": "Medicine", "zh_hans": "药品", "zh_hant": "藥品"},
    "ammo": {"en": "Pistol ammunition", "zh_hans": "手枪弹药", "zh_hant": "手槍彈藥"},
    "key": {"en": "Brass key", "zh_hans": "黄铜钥匙", "zh_hant": "黃銅鑰匙"},
}
DESCRIPTIONS = {
    "old_inscription": {"pages": [
        {"en": "An old inscription reads: Only those who remember may pass.",
         "zh_hans": "古老的铭文写着：唯有铭记之人，方可通行。",
         "zh_hant": "古老的銘文寫著：唯有銘記之人，方可通行。"},
        {"en": "There is a small button beneath the inscription. Press it?",
         "zh_hans": "铭文下方有一个小按钮。按下它吗？",
         "zh_hant": "銘文下方有一個小按鈕。按下它嗎？"}],
        "choices": [{"label": "yes", "handler": "inscription_button"}, {"label": "no"}]},
    "statue": {"pages": [{"en": "The statue's expression is serene. Someone has left fresh offerings at its feet.",
                           "zh_hans": "雕像神情安详。有人在它脚下放了新鲜的供品。",
                           "zh_hant": "雕像神情安詳。有人在它腳下放了新鮮的供品。"}]},
}


def inscription_button(arena, event):
    import g_puzzles
    import g_interactions
    arena = g_puzzles.set_fact(arena, "inscription_button:" + str(event["target"]), True)
    return g_interactions.open_dialogue(arena, ["You hear a faint click inside the wall."])


HANDLERS = {"inscription_button": inscription_button}
