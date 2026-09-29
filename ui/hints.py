"""One sentence per rail section, in the one place everything can read it.

Three surfaces need the same sentence and used to have none of them: the rail
button's tooltip (NavButton never called setToolTip at all, so the rail was ten
icons and ten nouns), the Go menu entry's status tip, and the intro line at the
top of the section itself - which only three of the ten sections had.

It lives here rather than in ui/main_window.py because the views need it too and
a view importing MainWindow would be a cycle. Keyed by NAV_ITEMS' own key, so a
missing entry is a test failure rather than a silently empty tooltip.
"""

NAV_HINTS = {
    "images": ("Build one image from a character spec, sample several, or derive a "
               "batch from a photo you already have."),
    "look": ("The tuning toolkits - light, framing, camera angle, colour, pose, "
             "style, capture. Each builds a phrase you apply into the Images prompt."),
    "videos": "Turn a still into a Kling clip, with the movement glossary behind it.",
    "influencer_studio": ("Build and save a recurring person, then compose them into "
                          "a Subject description."),
    "ads": ("The five-beat UGC video ad, and the static ad with its ten "
            "creative-direction commands."),
    "cats": ("A pet story in scenes, with its storyboard, edit sheet and a free-form "
             "custom prompt."),
    "sound": "Sound-effect prompts, text to speech, and voice cloning.",
    "assistant": "Ask for help in conversation, or run the one-shot prompt tools.",
    "activity": "Everything you have generated, and what the ratings say is working.",
    "settings": "Provider, model, keys, theme and where files are written.",
}
