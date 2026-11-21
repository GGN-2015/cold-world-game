"""Render the repository's existing handbook into the game's browser wiki."""

import html
import json
import posixpath
import re
from urllib.parse import quote, unquote, urlsplit

if __package__:
    from .wiki_roles import ROLES
else:
    from wiki_roles import ROLES


PLAYER_PAGES = {
    "wiki/README.md", "wiki/items.md", "wiki/monsters.md", "wiki/ordinary-chest.md", "wiki/roles.md",
    "items/foods.md", "items/tools.md", "items/weapons.md",
    "world/survival.md", "world/combat.md", "world/world.md",
    "building/building.md", "building/machines.md", "building/outdoor-facilities.md",
    "building/economy.md", "building/biome-devices.md", "guide/inventory.md", "guide/controls.md", "guide/arena.md",
}

HEADING = re.compile(r"^(#{1,6}) +(.+)$")
INLINE = re.compile(r"(!?)\[([^\]\n]+)\]\(([^)\s]+)\)|`([^`\n]+)`|\*\*([^*\n]+)\*\*")
LIST = re.compile(r"^(?:([-*])|(\d+)\.) +(.+)$")
ROW_SEPARATOR = re.compile(r"^\|(?:\s*:?-{2,}:?\s*\|)+$")


def slug(text):
    return re.sub(r"[^\w\s-]", "", text.strip().lower()).replace(" ", "-")


def sections(markdown):
    lines = markdown.splitlines()
    headings = [(index, len(match[1]), match[2]) for index, line in enumerate(lines) if (match := HEADING.match(line))]
    for i, (start, depth, title) in enumerate(headings):
        end = next((index for index, later_depth, _ in headings[i + 1:] if later_depth <= depth), len(lines))
        yield depth, title, "\n".join(lines[start + 1:end])


def cells(line):
    return [part.strip() for part in line.strip().strip("|").split("|")]


def quick_stats(markdown):
    stats = {}
    labels = []
    for line in markdown.splitlines():
        if line.startswith("| 物品及 ID |") or line.startswith("| 怪物及 ID |"):
            labels = cells(line)
        elif labels and line.startswith("| "):
            row = cells(line)
            identifier = re.search(r"`([a-z_]+)`", row[0])
            if identifier and len(row) == len(labels):
                stats[identifier[1]] = list(zip(labels[1:], row[1:]))
    return stats


class Markup:
    def __init__(self, pages, article_routes):
        self.pages = pages
        self.article_routes = article_routes

    def href(self, source, href):
        target = urlsplit(href)
        if target.scheme in {"https", "http"}:
            return href
        if target.scheme or target.netloc:
            return None
        path = posixpath.normpath(posixpath.join(posixpath.dirname(source), unquote(target.path))) if target.path else source
        anchor = slug(unquote(target.fragment)) if target.fragment else ""
        if path.startswith("../cold_world_game/static/assets/"):
            return "/static/assets/" + quote(posixpath.basename(path))
        if path in {"../README.md", "wiki/README.md", "README.md"} and not anchor:
            return "#/"
        if route := self.article_routes.get((path, anchor)):
            return route
        if path in self.pages:
            href = "#/page/" + quote(path, safe="")
            return f"{href}/{quote(anchor)}" if anchor else href
        return None

    def inline(self, text, source):
        output = []
        position = 0
        for match in INLINE.finditer(text):
            output.append(html.escape(text[position:match.start()]))
            image, label, target, code, bold = match.groups()
            if code is not None:
                output.append(f"<code>{html.escape(code)}</code>")
            elif bold is not None:
                output.append(f"<strong>{self.inline(bold, source)}</strong>")
            else:
                href = self.href(source, target)
                if not href:
                    output.append(html.escape(label))
                elif image and href.startswith("/static/assets/"):
                    output.append(f'<img src="{html.escape(href, quote=True)}" alt="{html.escape(label, quote=True)}" loading="lazy">')
                else:
                    output.append(f'<a href="{html.escape(href, quote=True)}">{html.escape(label)}</a>')
            position = match.end()
        output.append(html.escape(text[position:]))
        return "".join(output)

    def render(self, source, markdown):
        lines = markdown.splitlines()
        output = []
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
            elif line.startswith("```"):
                i += 1
                code = []
                while i < len(lines) and not lines[i].startswith("```"):
                    code.append(lines[i])
                    i += 1
                output.append("<pre><code>" + html.escape("\n".join(code)) + "</code></pre>")
                i += 1
            elif heading := HEADING.match(line):
                depth, title = max(2, len(heading[1])), heading[2]
                anchor = html.escape(slug(title), quote=True)
                if route := self.article_routes.get((source, slug(title))):
                    content = f'<a href="{route}">{self.inline(title, source)}</a>'
                else:
                    content = self.inline(title, source)
                output.append(f'<h{depth} id="{anchor}">{content}</h{depth}>')
                i += 1
            elif line.startswith("|") and i + 1 < len(lines) and ROW_SEPARATOR.match(lines[i + 1].strip()):
                header = "".join(f'<th scope="col">{self.inline(col, source)}</th>' for col in cells(line))
                output.append(f'<div class="wiki-table"><table><thead><tr>{header}</tr></thead><tbody>')
                i += 2
                while i < len(lines) and lines[i].strip().startswith("|"):
                    row = "".join(f"<td>{self.inline(col, source)}</td>" for col in cells(lines[i]))
                    output.append(f"<tr>{row}</tr>")
                    i += 1
                output.append("</tbody></table></div>")
            elif entry := LIST.match(line):
                tag = "ol" if entry[2] else "ul"
                output.append(f"<{tag}>")
                while i < len(lines) and (entry := LIST.match(lines[i].strip())) and (tag == "ol") == bool(entry[2]):
                    output.append(f"<li>{self.inline(entry[3], source)}</li>")
                    i += 1
                output.append(f"</{tag}>")
            else:
                output.append(f"<p>{self.inline(line, source)}</p>")
                i += 1
        return "\n".join(output)


def article_locations(manual):
    group_pages = {
        "weapon": "items/weapons.md", "food": "items/foods.md",
        "tool": "items/tools.md", "facility": "building/machines.md",
    }
    location = {kind: (group, group_pages[group], manual.names[kind][0])
                for group, kinds in manual.categories.items() for kind in kinds}
    for kind in manual.available - location.keys():
        location[kind] = ("facility", "building/economy.md", "金钱属性") if kind == "coin" else (
            "facility", "building/building.md", manual.names[kind][0],
        )
    for kind in ("park_bench", "mounted_gun", "service_gun"):
        location[kind] = "facility", "building/outdoor-facilities.md", manual.names[kind][0]
    for kind in ("cable_station", "bridge_pier", "bridge_deck", "street_lamp"):
        location[kind] = "facility", "building/biome-devices.md", manual.names[kind][0]
    location.update({kind: ("monster", "world/combat.md", name) for kind, name in manual.monsters.items()})
    return location


def render_roles(manual):
    labels = {"weapon": "武器与弹药", "tool": "工具与道具", "food": "食品", "facility": "建筑与设施", "monster": "怪物"}
    locations = article_locations(manual)
    lines = ["# 条目定位", "", "按当前可取得的武器、用品和可遇到的设施、怪物查用途。名称可打开完整机制和获取方式。", ""]
    for group, label in labels.items():
        lines += [f"## {label}", "", "| 条目 | 用途 |", "| --- | --- |"]
        lines.extend(f"| [{manual.names.get(kind, (title,))[0]}](../{path}#{title}) | {ROLES[kind]} |"
                     for kind, (entry_group, path, title) in sorted(locations.items()) if entry_group == group)
        lines.append("")
    return lines


def generate(root, manual, generated):
    docs = {path: generated[path] if path in generated else (root / "docs" / path).read_text(encoding="utf-8")
            for path in PLAYER_PAGES}
    section_map = {path: {slug(title): text for _, title, text in sections(markdown)}
                   for path, markdown in docs.items()}
    location = article_locations(manual)
    article_routes = {(path, slug(heading)): f"#/{'monster' if group == 'monster' else 'item'}/{kind}"
                      for kind, (group, path, heading) in location.items()}
    markup = Markup(docs, article_routes)
    item_stats = quick_stats(generated["wiki/items.md"])
    monster_stats = quick_stats(generated["wiki/monsters.md"])
    rules = manual.rules
    gun_like = rules.GUNS.keys() | {"flamethrower"}
    hand_tools = rules.EQUIPPED_ITEMS.keys() | rules.BUILDING_WANDS.keys() | {"repair_wrench", "lantern"}
    materials = {"papyrus", "spare_part", "quill"}
    entries = []
    for kind, (group, path, heading) in sorted(location.items()):
        name, english = manual.names.get(kind, (heading, kind.replace("_", " ").title()))
        source = section_map[path][slug(heading)]
        image = f"monster_{kind}" if group == "monster" else kind
        asset = root / "cold_world_game/static/assets" / f"{image}.png"
        if not asset.exists():
            raise ValueError(f"Missing wiki artwork: {image}")
        if (art := re.search(r"^!\[[^\]]+\]\([^)]*?/" + re.escape(image) + r"\.png\) *", source, re.MULTILINE)):
            source = source[:art.start()] + source[art.end():]
        stats = (monster_stats if group == "monster" else item_stats).get(kind, [])
        entry = {
            "id": kind, "name": name, "english": english, "group": group, "image": image, "role": ROLES[kind],
            "summary": [(label, markup.inline(value, "wiki/monsters.md" if group == "monster" else "wiki/items.md"))
                        for label, value in stats if value != "—"],
            "article": markup.render(path, source),
        }
        if group == "weapon":
            subtype = "ammo" if kind in rules.AMMO_PACKS else "melee" if kind in rules.MELEE_WEAPONS else "gun" if kind in gun_like else "throwable"
        elif group == "tool":
            if kind in rules.CREATIVE_ITEMS:
                subtype = "test"
            elif kind in hand_tools:
                subtype = "held"
            elif kind in rules.PASSIVE_ITEMS:
                subtype = "carried"
            elif kind in materials:
                subtype = "material"
            else:
                subtype = "consumable"
        elif group == "food":
            subtype = "drink" if kind in rules.DRINKS or kind == "cola" else "ready" if kind in rules.READY_TO_EAT_FOODS else "cook"
        elif group == "facility":
            subtype = {
                "park_bench": "outdoor", "fixed_heater": "outdoor", "mounted_gun": "outdoor", "service_gun": "outdoor",
                "cable_station": "crossing", "bridge_pier": "crossing", "bridge_deck": "crossing", "street_lamp": "crossing",
                "chest": "utility", "campfire": "utility", "piggy_bank": "utility",
            }.get(kind, "trade" if kind in rules.TRADING_MACHINES or kind == "coin" else "building")
        else:
            subtype = "biome" if kind in manual.wildlife.BIOME_GUARDS else "roaming"
        entry.update(subtype=subtype, tier=None if subtype == "test" else 1)
        entries.append(entry)

    pages = {}
    for path, markdown in sorted(docs.items()):
        headings = [(depth, title) for depth, title, _ in sections(markdown)]
        title = headings[0][1] if headings else path
        body = markdown.partition("\n")[2] if markdown.startswith("# ") else markdown
        pages[path] = {
            "title": title,
            "headings": [(slug(title), title) for depth, title in headings if depth == 2],
            "article": markup.render(path, body),
        }
    return json.dumps({
        "version": manual.profile["version"], "itemCount": len(manual.available),
        "monsterCount": len(manual.monsters), "entries": entries, "pages": pages,
    }, ensure_ascii=False, separators=(",", ":")) + "\n"
