import importlib.util
import re


def definitions(root, filename, attribute):
    specification = importlib.util.spec_from_file_location(attribute, root / "cold_world_game" / filename)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return getattr(module, attribute)


def illustrate(root, assets):
    source = (root / "cold_world_game/static/js/i18n.js").read_text(encoding="utf-8")
    names = dict(re.findall(r"'item\.([a-z_]+)': \['([^']+)'", source))
    names.update({"durian": "榴莲", "durian_peel": "榴莲皮"})
    for filename, attribute in (("expansion.py", "EXPANSION_ITEMS"), ("room_machines.py", "ROOM_MACHINES")):
        names.update({kind: definition["name"][0] for kind, definition in definitions(root, filename, attribute).items()})
    names = {kind: name for kind, name in names.items() if kind in assets}
    aliases = {name: kind for kind, name in names.items()}
    aliases.update({"饺子": "dumplings", "馄饨": "wontons", "猪蹄": "pork_trotters", "牛肉": "beef", "羊肉": "lamb", "沙丁鱼": "sardines", "金枪鱼": "tuna", "牛肉丸": "beef_balls", "火锅蔬菜": "hotpot_vegetables", "地板": "floor", "栅栏": "fence", "火堆": "campfire"})
    image_pattern = re.compile(r"!\[[^\]]*\]\(\.\./cold_world_game/static/assets/[a-z0-9_]+\.png\)")

    def matching(text, explicit=False):
        kinds = [kind for kind in re.findall(r"`([a-z_]+)`", text) if kind in names]
        if not explicit:
            for name in sorted(aliases, key=len, reverse=True):
                if name in text:
                    kinds.append(aliases[name])
                    text = text.replace(name, "")
        return list(dict.fromkeys(kinds))

    def images(kinds):
        return " ".join(f"![{names[kind]}](../cold_world_game/static/assets/{assets[kind]['file']})" for kind in kinds)

    for path in sorted((root / "docs").glob("*.md")):
        if path.stem in {"combat", "foods", "tools", "weapons", "machines", "building", "economy"}:
            continue
        original = path.read_text(encoding="utf-8")
        source = image_pattern.sub("", original)
        output = []
        fenced = False
        for line in source.splitlines():
            if line.lstrip().startswith("```"):
                fenced = not fenced
            if not fenced and re.match(r"#{2,3} ", line):
                output.append(line)
                kinds = matching(line)
                if kinds:
                    output += ["", images(kinds), ""]
                continue
            output.append(line.rstrip())
        updated = re.sub(r"\n{3,}", "\n\n", "\n".join(output)).strip() + "\n"
        if updated != original:
            path.write_text(updated, encoding="utf-8", newline="\n")
