import math

from PIL import Image, ImageDraw


def creature(kind, direction, pose):
    image = Image.new("RGBA", (32, 32))
    drawing = ImageDraw.Draw(image)
    drawing.ellipse((5, 26, 28, 30), fill="#42616d66")
    lift = (0, -1, 0, 1, 0)[pose]
    stride = (0, 2, 1, -2, -1)[pose]
    if kind == "crawler":
        for horizontal in (8, 15, 23):
            drawing.line((horizontal, 20 + lift, horizontal - stride - 3, 27), fill="#433b58", width=3)
        drawing.rounded_rectangle((5, 14 + lift, 27, 25 + lift), radius=5, fill="#3e3c57")
        drawing.rounded_rectangle((7, 15 + lift, 26, 23 + lift), radius=4, fill="#b4a4cc")
        drawing.line((9, 16 + lift, 23, 16 + lift), fill="#e0d8ee", width=2)
        drawing.polygon(((18, 15 + lift), (20, 10 + lift), (22, 15 + lift)), fill="#e6e4f1")
        eyes = (9, 18) if direction == "left" else (22, 18) if direction == "right" else (12, 19)
        if direction != "up":
            drawing.rectangle((eyes[0], eyes[1] + lift, eyes[0] + 2, eyes[1] + 1 + lift), fill="#e3748f")
            if direction == "down":
                drawing.rectangle((20, 19 + lift, 22, 20 + lift), fill="#e3748f")
    elif kind == "armored":
        drawing.line((12, 22, 10 + stride, 28), fill="#263b55", width=5)
        drawing.line((22, 22, 24 - stride, 28), fill="#263b55", width=5)
        drawing.polygon(((5, 12 + lift), (11, 7 + lift), (24, 7 + lift), (29, 15 + lift), (25, 26 + lift), (10, 26 + lift)), fill="#23394f")
        drawing.polygon(((7, 13 + lift), (12, 9 + lift), (23, 9 + lift), (27, 15 + lift), (23, 24 + lift), (11, 24 + lift)), fill="#577ca5")
        drawing.polygon(((11, 11 + lift), (17, 8 + lift), (23, 12 + lift), (18, 18 + lift)), fill="#b5ddeb")
        drawing.line((8, 20 + lift, 25, 20 + lift), fill="#8aafd0", width=2)
        if direction != "up":
            eye_x = 10 if direction == "left" else 22 if direction == "right" else 13
            drawing.rectangle((eye_x, 14 + lift, eye_x + 2, 15 + lift), fill="#ffd498")
            if direction == "down":
                drawing.rectangle((21, 14 + lift, 23, 15 + lift), fill="#ffd498")
    else:
        drawing.line((10, 22, 7 + stride, 28), fill="#6e453e", width=3)
        drawing.line((21, 22, 25 - stride, 28), fill="#6e453e", width=3)
        drawing.polygon(((8, 20 + lift), (3, 12 + lift), (7, 15 + lift), (11, 16 + lift), (13, 23 + lift)), fill="#e6a46f")
        drawing.polygon(((9, 10 + lift), (8, 3 + lift), (14, 8 + lift), (20, 8 + lift), (25, 3 + lift), (25, 13 + lift), (27, 21 + lift), (20, 26 + lift), (11, 25 + lift), (7, 20 + lift)), fill="#684343")
        drawing.polygon(((11, 11 + lift), (10, 7 + lift), (14, 11 + lift), (21, 11 + lift), (23, 7 + lift), (23, 14 + lift), (25, 21 + lift), (19, 24 + lift), (12, 23 + lift), (9, 19 + lift)), fill="#dc9c69")
        if direction != "up":
            drawing.polygon(((11, 16 + lift), (23, 16 + lift), (18, 23 + lift)), fill="#fff0cc")
            eyes = (11, 20) if direction == "down" else (10,) if direction == "left" else (23,)
            for horizontal in eyes:
                drawing.rectangle((horizontal, 13 + lift, horizontal + 1, 14 + lift), fill="#763d48")
            drawing.rectangle((16, 19 + lift, 18, 20 + lift), fill="#443444")
    return image


def generate(save, animations, effects, traveler_frame, frozen_image):
    directions = ("down", "left", "right", "up")
    for kind in ("crawler", "armored", "stalker"):
        name = "monster_" + kind
        save(name, creature(kind, "down", 0))
        for frozen in (False, True):
            asset = name + ("_frozen" if frozen else "")
            sheet = Image.new("RGBA", (160, 128))
            for row, direction in enumerate(directions):
                for pose in range(5):
                    frame = creature(kind, direction, pose)
                    if frozen:
                        frame = frozen_image(frame, False, direction, pose)
                    sheet.alpha_composite(frame, (pose * 32, row * 32))
            if frozen:
                save(asset, frozen_image(creature(kind, "down", 0), False))
            save(asset + "_motion", sheet)
            animations[asset] = {"asset": asset + "_motion", "frame_width": 96, "frame_height": 96, "directions": directions, "idle_frame": 0, "walk_frames": [1, 2, 3, 4], "stride": 0.8 if kind == "crawler" else 1.1}
        death = Image.new("RGBA", (192, 32))
        for frame in range(6):
            image = creature(kind, "down", 0).rotate(-min(90, frame * 24), resample=Image.Resampling.NEAREST, center=(16, 20))
            image.putalpha(image.getchannel("A").point(lambda alpha: alpha * (255, 255, 240, 200, 125, 45)[frame] // 255))
            death.alpha_composite(image, (frame * 32, 0))
        save(name + "_death", death)
        effects[name + "_death"] = {"asset": name + "_death", "frame_width": 96, "frame_height": 96, "frames": 6, "duration": 0.65}
    for owned in (True, False):
        name = "player_seated" if owned else "player_other_seated"
        sheet = Image.new("RGBA", (160, 128))
        for row, direction in enumerate(directions):
            standing = traveler_frame("#cf784e" if owned else "#498a97", direction, 0)
            frame = Image.new("RGBA", (32, 32))
            frame.alpha_composite(standing.crop((0, 0, 32, 23)), (0, 3))
            drawing = ImageDraw.Draw(frame)
            drawing.line((13, 25, 23, 25, 24, 29), fill="#304b58", width=3)
            drawing.line((12, 24, 20, 24, 21, 28), fill="#6d7b79", width=3)
            for pose in range(5):
                sheet.alpha_composite(frame, (pose * 32, row * 32))
        save(name, sheet.crop((0, 0, 32, 32)))
        save(name + "_motion", sheet)
        animations[name] = {"asset": name + "_motion", "frame_width": 96, "frame_height": 96, "directions": directions, "idle_frame": 0, "walk_frames": [0], "stride": 1.5}
    mine = Image.new("RGBA", (32, 32))
    drawing = ImageDraw.Draw(mine)
    drawing.ellipse((4, 16, 28, 27), fill="#35555b")
    drawing.ellipse((6, 13, 26, 24), fill="#708e77", outline="#263e48", width=2)
    drawing.ellipse((12, 12, 20, 18), fill="#bac9a5", outline="#263e48")
    drawing.rectangle((15, 13, 17, 15), fill="#ed9b72")
    for horizontal in (8, 23):
        drawing.rectangle((horizontal, 20, horizontal + 1, 21), fill="#e6d9ac")
    save("landmine", mine)
    bench = Image.new("RGBA", (32, 32))
    drawing = ImageDraw.Draw(bench)
    for horizontal in (7, 24):
        drawing.line((horizontal, 10, horizontal, 28), fill="#324a53", width=3)
    for vertical in (8, 13):
        drawing.rounded_rectangle((3, vertical, 29, vertical + 3), radius=1, fill="#c79665", outline="#654f46")
    drawing.polygon(((5, 19), (27, 19), (30, 23), (2, 23)), fill="#d4a56e", outline="#654f46")
    drawing.line((6, 8, 26, 8), fill="#e7f1ec", width=2)
    save("park_bench", bench)
    for index, suffix in enumerate(("e", "se", "s", "sw", "w", "nw", "n", "ne")):
        gun = Image.new("RGBA", (32, 32))
        drawing = ImageDraw.Draw(gun)
        drawing.ellipse((5, 21, 28, 29), fill="#46615d")
        drawing.line((16, 17, 8, 27), fill="#364953", width=3)
        drawing.line((16, 17, 26, 27), fill="#364953", width=3)
        drawing.rounded_rectangle((10, 14, 22, 22), radius=2, fill="#789487", outline="#263e48", width=2)
        angle = index * math.pi / 4
        end = (round(16 + math.cos(angle) * 14), round(16 + math.sin(angle) * 11))
        drawing.line((16, 16, *end), fill="#263e48", width=5)
        drawing.line((16, 15, end[0], end[1] - 1), fill="#a4b6ae", width=2)
        drawing.rectangle((9, 19, 12, 24), fill="#ceb470")
        save("mounted_gun_" + suffix, gun)
        if index == 0:
            save("mounted_gun", gun)
