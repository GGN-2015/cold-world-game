import math

from PIL import Image, ImageDraw


def crawler_art(image, direction, pose):
    drawing = ImageDraw.Draw(image)
    step = (0, 2, 1, -2, -1)[pose]
    lift = (0, 0, -1, 0, -1)[pose]
    outline = "#303447"
    if direction == "right":
        for index, horizontal in enumerate((7, 13, 20)):
            reach = step if index % 2 == 0 else -step
            drawing.line((horizontal, 20 + lift, horizontal - 2 - reach, 25, horizontal - 4 - reach, 26), fill=outline, width=3)
            drawing.line((horizontal, 20 + lift, horizontal - 2 - reach, 24), fill="#625775", width=1)
        body = Image.new("RGBA", (32, 32))
        shell = ImageDraw.Draw(body)
        shell.polygon(((3, 17), (6, 12), (16, 11), (23, 14), (25, 21), (21, 24), (7, 24), (3, 21)), fill=outline)
        shell.polygon(((5, 17), (8, 14), (17, 13), (22, 16), (22, 21), (18, 23), (7, 22)), fill="#706184")
        shell.polygon(((6, 16), (9, 12), (15, 12), (16, 17), (11, 19)), fill="#aa9fbc")
        shell.polygon(((12, 13), (17, 12), (22, 15), (22, 18), (18, 19), (16, 16)), fill="#9182a6")
        shell.line((11, 15, 12, 19, 10, 22), fill="#4c455e", width=1)
        shell.line((17, 15, 18, 19, 16, 22), fill="#4c455e", width=1)
        shell.polygon(((6, 15), (8, 12), (11, 12), (12, 9), (14, 12), (18, 12), (20, 14), (16, 15), (12, 14), (10, 16)), fill="#e8edef")
        shell.line((8, 13, 10, 13), fill="#ffffff", width=1)
        shell.polygon(((21, 16), (26, 15), (29, 18), (29, 22), (26, 25), (21, 24), (19, 20)), fill=outline)
        shell.polygon(((22, 17), (26, 17), (28, 19), (27, 23), (22, 23), (21, 20)), fill="#8c7d9e")
        shell.rectangle((24, 18, 27, 20), fill="#4c3b51")
        shell.rectangle((25, 18, 27, 19), fill="#ff947f")
        shell.point((27, 18), fill="#ffe0ae")
        shell.polygon(((26, 23), (29, 24), (28, 27), (27, 25), (25, 25)), fill="#e5e9de")
        shell.rectangle((22, 23, 23, 25), fill="#c9ced0")
        image.alpha_composite(body, (0, lift))
        for index, horizontal in enumerate((7, 13, 20)):
            reach = -step if index % 2 == 0 else step
            drawing.line((horizontal, 22 + lift, horizontal + 2 + reach, 26, horizontal + reach, 28), fill=outline, width=3)
            drawing.line((horizontal, 22 + lift, horizontal + 2 + reach, 26), fill="#9988ac", width=1)
            drawing.line((horizontal + reach, 28, horizontal + reach + 2, 28), fill="#e2e8df", width=1)
        return
    for index, vertical in enumerate((15, 19, 23)):
        for side in (-1, 1):
            reach = step * side * (1 if index % 2 == 0 else -1)
            shoulder = 16 + side * 7
            knee = 16 + side * 10
            foot = 16 + side * 13
            drawing.line((shoulder, vertical + lift, knee, vertical + reach, foot, vertical + 3 + reach), fill=outline, width=3)
            drawing.line((shoulder, vertical + lift, knee, vertical + reach), fill="#9586a8", width=1)
            drawing.line((foot, vertical + 3 + reach, foot - side, vertical + 4 + reach), fill="#e2e8df", width=1)
    body = Image.new("RGBA", (32, 32))
    shell = ImageDraw.Draw(body)
    shell.polygon(((9, 10), (13, 8), (20, 8), (24, 11), (26, 19), (23, 25), (10, 25), (7, 20), (7, 14)), fill=outline)
    shell.polygon(((10, 12), (14, 10), (20, 10), (23, 13), (24, 19), (21, 23), (11, 23), (9, 19)), fill="#77698c")
    shell.polygon(((10, 13), (14, 10), (16, 11), (16, 20), (11, 21), (9, 17)), fill="#a99dbc")
    shell.polygon(((17, 11), (20, 10), (23, 14), (24, 18), (20, 20), (17, 18)), fill="#8e7da2")
    for vertical in (14, 18):
        shell.line((10, vertical, 15, vertical + 1, 17, vertical + 1, 23, vertical), fill="#4e465f", width=1)
    shell.polygon(((10, 12), (13, 10), (14, 7), (16, 10), (19, 9), (21, 6), (23, 11), (21, 13), (17, 12), (15, 14), (13, 12)), fill="#edf0f0")
    shell.line((12, 11, 14, 10), fill="#ffffff", width=1)
    if direction == "down":
        shell.polygon(((11, 18), (15, 17), (20, 17), (24, 20), (23, 24), (20, 26), (13, 26), (10, 23)), fill=outline)
        shell.polygon(((12, 19), (16, 19), (20, 19), (22, 21), (21, 24), (13, 24), (12, 22)), fill="#9885a7")
        shell.rectangle((12, 20, 14, 21), fill="#f18d86")
        shell.rectangle((20, 20, 22, 21), fill="#f18d86")
        shell.point((12, 20), fill="#ffe4b5")
        shell.point((22, 20), fill="#ffe4b5")
        shell.rectangle((15, 23, 19, 24), fill=outline)
        shell.polygon(((12, 24), (15, 25), (14, 28), (12, 26)), fill="#e8eadd")
        shell.polygon(((20, 25), (23, 24), (23, 26), (21, 28)), fill="#e8eadd")
    else:
        shell.polygon(((11, 10), (13, 7), (20, 7), (23, 10), (21, 13), (13, 13)), fill=outline)
        shell.polygon(((13, 10), (15, 8), (20, 9), (21, 11), (17, 12)), fill="#aea3bf")
        shell.line((15, 8, 19, 8), fill="#e7eced", width=1)
        shell.polygon(((12, 18), (16, 19), (21, 18), (21, 22), (17, 25), (12, 22)), fill="#8a799e")
        shell.line((16, 20, 16, 23), fill="#c4b8d2", width=1)
    image.alpha_composite(body, (0, lift))


def armored_art(image, direction, pose):
    drawing = ImageDraw.Draw(image)
    step = (0, 2, 1, -2, -1)[pose]
    lift = (0, 0, -1, 0, -1)[pose]
    outline = "#253c4b"
    for horizontal, reach in ((10, step), (21, -step)):
        drawing.polygon(((horizontal - 3, 22), (horizontal + 3, 22), (horizontal + 3 + reach, 28), (horizontal + 2 + reach, 29), (horizontal - 4 + reach, 29), (horizontal - 4 + reach, 27)), fill=outline)
        drawing.rectangle((horizontal - 2 + reach, 26, horizontal + 1 + reach, 27), fill="#668b9b")
        drawing.line((horizontal - 3 + reach, 28, horizontal + 1 + reach, 28), fill="#d3e4df", width=1)
    body = Image.new("RGBA", (32, 32))
    armor = ImageDraw.Draw(body)
    if direction == "right":
        armor.polygon(((5, 10), (9, 7), (18, 8), (24, 12), (26, 22), (23, 26), (10, 26), (5, 21)), fill=outline)
        armor.polygon(((7, 12), (10, 9), (17, 10), (23, 13), (23, 22), (20, 24), (11, 24), (7, 20)), fill="#4b768d")
        armor.polygon(((4, 12), (7, 7), (8, 3), (12, 7), (15, 5), (19, 11), (17, 18), (9, 21), (4, 18)), fill=outline)
        armor.polygon(((6, 12), (8, 8), (9, 5), (12, 10), (15, 8), (17, 12), (15, 17), (9, 19), (6, 17)), fill="#9fd4e1")
        armor.polygon(((8, 8), (9, 5), (12, 10), (10, 15), (7, 15)), fill="#ecf5ed")
        armor.line((12, 10, 14, 12, 11, 17), fill="#5f9cb9", width=1)
        armor.polygon(((19, 10), (24, 10), (27, 13), (28, 17), (25, 20), (19, 19), (17, 15)), fill=outline)
        armor.polygon(((20, 12), (24, 12), (26, 14), (25, 17), (21, 18), (19, 15)), fill="#526976")
        armor.rectangle((23, 13, 26, 14), fill="#ffce88")
        armor.point((26, 13), fill="#fff6cc")
        armor.polygon(((21, 16), (26, 16), (28, 18), (25, 20), (23, 19), (20, 20), (19, 18)), fill="#e1eee6")
        armor.rectangle((26, 16, 28, 17), fill=outline)
        armor.line((12, 22, 20, 23), fill="#8fb3bd", width=1)
        arm_shift = step // 2
        armor.polygon(((21, 18), (26, 17), (29, 21 + arm_shift), (28, 25 + arm_shift), (23, 25 + arm_shift), (20, 22)), fill=outline)
        armor.polygon(((23, 19), (26, 19), (27, 22 + arm_shift), (24, 23 + arm_shift), (22, 21)), fill="#7cb1c6")
        armor.line((24, 24 + arm_shift, 27, 24 + arm_shift), fill="#e4efe6", width=1)
    else:
        armor.polygon(((8, 11), (12, 8), (20, 8), (25, 12), (25, 23), (22, 26), (10, 26), (7, 23)), fill=outline)
        armor.polygon(((10, 12), (15, 10), (21, 11), (23, 15), (23, 23), (20, 24), (11, 24), (9, 21)), fill="#42697f")
        for side in (-1, 1):
            horizontal = 16 + side * 9
            reach = step * side // 2
            armor.polygon(((horizontal - 2, 15), (horizontal + 2, 14), (horizontal + 3, 21 + reach), (horizontal + 2, 24 + reach), (horizontal - 3, 24 + reach), (horizontal - 4, 21 + reach)), fill=outline)
            armor.polygon(((horizontal - 2, 16), (horizontal + 1, 16), (horizontal + 1, 21 + reach), (horizontal - 2, 22 + reach)), fill="#689aaf")
            armor.line((horizontal - 2, 23 + reach, horizontal + 1, 23 + reach), fill="#e0ece4", width=1)
            armor.polygon(((horizontal - 5, 12), (horizontal - 3, 7), (horizontal - 2, 5), (horizontal + 3, 8), (horizontal + 5, 14), (horizontal + 2, 18), (horizontal - 3, 17)), fill=outline)
            armor.polygon(((horizontal - 3, 12), (horizontal - 2, 7), (horizontal + 2, 9), (horizontal + 3, 13), (horizontal + 1, 16), (horizontal - 2, 15)), fill="#8fc6da")
            armor.polygon(((horizontal - 3, 11), (horizontal - 2, 7), (horizontal + 1, 9), (horizontal, 12)), fill="#e8f2ec")
        if direction == "down":
            armor.polygon(((9, 8), (12, 5), (20, 5), (23, 8), (24, 14), (21, 20), (11, 20), (8, 14)), fill=outline)
            armor.polygon(((11, 9), (13, 7), (19, 7), (21, 9), (21, 14), (19, 17), (12, 17), (10, 14)), fill="#536d7b")
            armor.polygon(((10, 9), (11, 6), (14, 5), (16, 2), (19, 5), (21, 6), (22, 10), (18, 9), (16, 11), (13, 9)), fill="#a7d7e5")
            armor.polygon(((12, 7), (14, 5), (16, 2), (17, 6), (15, 8)), fill="#edf5ed")
            armor.rectangle((11, 12, 14, 13), fill="#ffcb85")
            armor.rectangle((18, 12, 21, 13), fill="#ffcb85")
            armor.point((11, 12), fill="#fff1bf")
            armor.point((21, 12), fill="#fff1bf")
            armor.polygon(((11, 16), (14, 15), (18, 15), (21, 16), (20, 19), (18, 18), (16, 20), (14, 18), (12, 19)), fill="#e6eee5")
            armor.rectangle((15, 15, 17, 16), fill=outline)
            armor.polygon(((11, 20), (16, 22), (21, 20), (20, 23), (16, 25), (12, 23)), fill="#79a8bd")
            armor.line((12, 20, 16, 21, 20, 20), fill="#b4d7df", width=1)
        else:
            armor.polygon(((10, 8), (12, 5), (20, 5), (23, 9), (23, 17), (20, 23), (16, 26), (11, 23), (9, 17)), fill=outline)
            for vertical, half_width in ((9, 5), (14, 6), (19, 5)):
                armor.polygon(((16 - half_width, vertical), (16, vertical - 3), (16 + half_width, vertical), (16 + half_width - 1, vertical + 4), (16, vertical + 6), (17 - half_width, vertical + 3)), fill="#78aec5")
                armor.line((17 - half_width, vertical, 16, vertical - 2, 15 + half_width, vertical), fill="#d2e9e8", width=1)
                armor.line((16, vertical, 16, vertical + 4), fill="#4f879f", width=1)
            armor.polygon(((13, 7), (16, 2), (19, 7), (16, 10)), fill="#b6e1e8")
            armor.line((16, 4, 16, 7), fill="#f5f7eb", width=1)
    image.alpha_composite(body, (0, lift))


def stalker_art(image, direction, pose):
    drawing = ImageDraw.Draw(image)
    outline = "#394350"
    step = (0, 2, 1, -2, -1)[pose]
    lift = (0, 0, -1, 0, -1)[pose]
    for horizontal, reach in ((11, step), (21, -step)):
        drawing.line((horizontal, 21, horizontal + reach, 27), fill=outline, width=3)
        drawing.line((horizontal + reach - 1, 28, horizontal + reach + 1, 28), fill="#e5e8d9", width=1)
    body = Image.new("RGBA", (32, 32))
    fur = ImageDraw.Draw(body)
    if direction == "right":
        fur.polygon(((11, 17), (7, 16), (5, 12), (2, 14), (2, 20), (5, 24), (11, 25), (15, 22)), fill=outline)
        fur.polygon(((10, 19), (6, 18), (4, 15), (4, 20), (7, 23), (12, 23)), fill="#ebe9d7")
        fur.polygon(((11, 19), (8, 17), (9, 21), (12, 23), (14, 21)), fill="#ca9471")
        fur.polygon(((9, 16), (14, 13), (21, 14), (25, 18), (24, 23), (20, 25), (11, 24), (8, 21)), fill=outline)
        fur.polygon(((11, 17), (15, 15), (21, 16), (23, 19), (22, 22), (19, 23), (12, 22), (10, 20)), fill="#cd9872")
        fur.line((12, 17, 16, 16, 19, 17), fill="#eecb98", width=1)
        fur.polygon(((13, 21), (18, 21), (22, 19), (22, 22), (18, 24), (13, 23)), fill="#e7e6d6")
        fur.polygon(((18, 12), (18, 5), (23, 8), (25, 5), (26, 12), (28, 14), (30, 16), (28, 20), (22, 22), (18, 19), (16, 15)), fill=outline)
        fur.polygon(((20, 11), (20, 8), (23, 11), (24, 9), (24, 13), (27, 15), (28, 17), (25, 19), (22, 20), (19, 17), (18, 14)), fill="#e0b384")
        fur.polygon(((19, 15), (22, 16), (25, 15), (28, 17), (25, 19), (22, 21), (20, 18), (18, 17)), fill="#f0ecda")
        fur.line((23, 12, 25, 13), fill="#674f4d", width=1)
        fur.point((24, 12), fill="#faf0bc")
        fur.rectangle((28, 16, 30, 17), fill=outline)
        fur.line((25, 19, 27, 18), fill="#986b5a", width=1)
        for horizontal, reach in ((12, -step), (22, step)):
            fur.line((horizontal, 22, horizontal + reach, 27), fill=outline, width=3)
            fur.line((horizontal, 22, horizontal + reach, 25), fill="#bc8465", width=1)
            fur.line((horizontal + reach - 1, 28, horizontal + reach + 1, 28), fill="#ebe9d9", width=1)
    else:
        if direction == "down":
            fur.polygon(((12, 15), (9, 11), (5, 10), (3, 14), (4, 20), (7, 24), (13, 25), (16, 21)), fill=outline)
            fur.polygon(((11, 17), (8, 14), (6, 12), (5, 15), (6, 20), (9, 23), (13, 23)), fill="#e7e6d6")
            fur.polygon(((11, 17), (8, 15), (8, 19), (11, 22), (14, 21)), fill="#c99472")
        fur.polygon(((11, 13), (17, 11), (23, 14), (25, 21), (22, 26), (12, 26), (9, 22)), fill=outline)
        fur.polygon(((13, 15), (17, 13), (21, 15), (23, 21), (20, 24), (13, 24), (11, 21)), fill="#cc9976")
        fur.line((16, 16, 16, 22), fill="#e1b889", width=2)
        fur.polygon(((9, 13), (9, 4), (14, 8), (19, 8), (24, 4), (25, 13), (27, 17), (24, 22), (21, 23), (17, 26), (12, 24), (8, 21), (7, 17)), fill=outline)
        fur.polygon(((11, 12), (11, 8), (14, 11), (19, 10), (22, 8), (22, 13), (24, 17), (22, 20), (18, 23), (13, 22), (10, 19), (9, 16)), fill="#dfb487")
        if direction == "down":
            fur.polygon(((10, 16), (14, 17), (17, 19), (21, 16), (24, 16), (22, 20), (18, 24), (15, 23), (11, 20)), fill="#f1ecdc")
            fur.line((11, 14, 14, 15), fill="#775748", width=1)
            fur.line((19, 15, 22, 14), fill="#775748", width=1)
            fur.point((12, 14), fill="#faf0bc")
            fur.point((21, 14), fill="#faf0bc")
            fur.rectangle((15, 20, 18, 21), fill=outline)
            fur.line((16, 22, 17, 22), fill="#967059", width=1)
        else:
            fur.line((13, 12, 15, 15, 14, 18), fill="#ba8668", width=1)
            fur.line((20, 12, 18, 15, 19, 18), fill="#eed5aa", width=1)
            fur.polygon(((14, 20), (18, 19), (22, 21), (24, 25), (22, 28), (17, 29), (12, 27), (11, 24)), fill=outline)
            fur.polygon(((15, 21), (18, 21), (21, 23), (22, 25), (20, 27), (16, 27), (13, 25)), fill="#e9e8d8")
            fur.polygon(((15, 21), (18, 21), (20, 23), (18, 25), (15, 24)), fill="#c79473")
    image.alpha_composite(body, (0, lift))


def creature(kind, direction, pose):
    if direction == "left":
        return creature(kind, "right", pose).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    image = Image.new("RGBA", (32, 32))
    drawing = ImageDraw.Draw(image)
    drawing.ellipse((5, 26, 28, 30), fill="#42616d66")
    if kind == "crawler":
        crawler_art(image, direction, pose)
    elif kind == "armored":
        armored_art(image, direction, pose)
    else:
        stalker_art(image, direction, pose)
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
            image = creature(kind, "down", 0).rotate(-min(90, frame * 24), resample=Image.Resampling.NEAREST, center=(16, 16))
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
