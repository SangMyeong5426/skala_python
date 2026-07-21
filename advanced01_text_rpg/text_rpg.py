"""텍스트 기반 미니 RPG 게임 - 파이썬 입문용 실습 프로젝트"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Literal

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
SAVE_FILE = BASE_DIR / "savegame.json"


def _load_json(filename: str) -> dict:
    return json.loads((DATA_DIR / filename).read_text(encoding="utf-8"))


# 장비 부위별로 가질 수 있는 스탯과, 레벨1·일반등급 기준 수치 범위
_equipment_data = _load_json("equipment.json")
EQUIPMENT_PARTS = _equipment_data["parts"]

# (등급명, 드랍 확률 가중치, 스탯 배율) - 가중치 합 100 = 고정 드랍 확률
GRADES = [(g["name"], g["weight"], g["multiplier"]) for g in _equipment_data["grades"]]
GRADE_NAMES = [g[0] for g in GRADES]
GRADE_WEIGHTS = [g[1] for g in GRADES]
GRADE_MULTIPLIER = {g[0]: g[2] for g in GRADES}
GRADE_SELL_PRICE = {g["name"]: g["sell_price"] for g in _equipment_data["grades"]}

# (몬스터명, 출현 가중치, 전투력 배율) - 가중치 합 100 = 고정 출현 확률
# power가 클수록 플레이어 레벨 대비 훨씬 강해져서, 레벨업만으로는 못 이기고 장비가 필요해진다.
_monster_data = _load_json("monsters.json")
MONSTERS = _monster_data["monsters"]
BOSS_TEMPLATE = _monster_data["boss"]
BOSS_LEVEL_REQUIREMENT = BOSS_TEMPLATE["level_requirement"]

# (등급명, HP 회복량, 가격)
_potion_data = _load_json("potions.json")
POTIONS = _potion_data["potions"]
POTION_NAMES = [p["name"] for p in POTIONS]
POTION_HEAL = {p["name"]: p["heal"] for p in POTIONS}
POTION_PRICE = {p["name"]: p["price"] for p in POTIONS}

_balance_data = _load_json("balance.json")
ATTACK_GROWTH_PER_LEVEL = _balance_data["attack_growth_per_level"]
HP_GROWTH_PER_LEVEL = _balance_data["hp_growth_per_level"]
FLEE_FAIL_CHANCE = _balance_data["flee_fail_chance"]
LEVEL_UP_HP_GAIN = _balance_data["level_up_hp_gain"]
LEVEL_UP_ATTACK_GAIN = _balance_data["level_up_attack_gain"]

BattleResult = Literal["alive", "dead", "cleared"]


@dataclass
class Equipment:
    part: str
    grade: str
    level: int
    attack: int = 0
    hp: int = 0

    def __str__(self) -> str:
        stats = [
            s
            for s in (
                f"공격력+{self.attack}" if self.attack else "",
                f"HP+{self.hp}" if self.hp else "",
            )
            if s
        ]
        return f"[{self.grade}] {self.part} ({', '.join(stats)}) Lv.{self.level}"


def _starting_potions() -> dict:
    potions = {name: 0 for name in POTION_NAMES}
    potions[POTION_NAMES[0]] = 2
    return potions


@dataclass
class Character:
    name: str
    hp: int = 100
    base_max_hp: int = 100
    base_attack: int = 10
    level: int = 1
    exp: int = 0
    gold: int = 50
    potions: dict = field(default_factory=_starting_potions)
    equipped: dict = field(default_factory=lambda: {part: None for part in EQUIPMENT_PARTS})
    equipment_inventory: list = field(default_factory=list)


def effective_attack(character: Character) -> int:
    return character.base_attack + sum(e.attack for e in character.equipped.values() if e)


def effective_max_hp(character: Character) -> int:
    return character.base_max_hp + sum(e.hp for e in character.equipped.values() if e)


def create_character() -> Character:
    name = input("모험가의 이름을 입력하세요: ").strip() or "이름없는용사"
    print(f"\n환영합니다, {name}님! 모험을 시작합니다.\n")
    return Character(name=name)


def save_game(character: Character) -> None:
    try:
        SAVE_FILE.write_text(
            json.dumps(asdict(character), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print("게임을 저장했습니다.")
    except OSError as e:
        print(f"저장 실패: {e}")


def load_game() -> Character | None:
    try:
        data = json.loads(SAVE_FILE.read_text(encoding="utf-8"))
        if isinstance(data.get("potions"), int):
            legacy_count = data["potions"]
            data["potions"] = {name: 0 for name in POTION_NAMES}
            data["potions"][POTION_NAMES[0]] = legacy_count
        data["equipped"] = {
            part: (Equipment(**item) if item else None) for part, item in data["equipped"].items()
        }
        data["equipment_inventory"] = [Equipment(**item) for item in data["equipment_inventory"]]
        print("저장된 게임을 불러왔습니다.")
        return Character(**data)
    except FileNotFoundError:
        print("저장된 게임이 없습니다.")
        return None
    except (json.JSONDecodeError, KeyError, TypeError):
        print("저장 파일이 손상되었습니다.")
        return None


def show_status(character: Character) -> None:
    print("\n--- 상태 ---")
    print(f"이름: {character.name}  Lv.{character.level}")
    print(
        f"HP: {character.hp}/{effective_max_hp(character)}  "
        f"공격력: {effective_attack(character)} (기본 {character.base_attack})"
    )
    total_potions = sum(character.potions.values())
    print(f"EXP: {character.exp}/{character.level * 100}  골드: {character.gold}  포션: {total_potions}개")
    if total_potions:
        detail = ", ".join(f"{name} {cnt}개" for name, cnt in character.potions.items() if cnt)
        print(f"  ({detail})")
    print("\n[장착 장비]")
    for part, item in character.equipped.items():
        print(f"  {part}: {item if item else '(없음)'}")
    if character.equipment_inventory:
        print(f"\n미착용 장비 {len(character.equipment_inventory)}개 보유 중 (4번 메뉴에서 관리, 상점에서 판매 가능)")
    if character.level >= BOSS_LEVEL_REQUIREMENT:
        print(f"\n탐험 시 {BOSS_TEMPLATE['name']}이(가) 나타납니다. 쓰러뜨리면 게임 클리어!")
    print("------------\n")


def level_up(character: Character) -> None:
    while character.exp >= character.level * 100:
        character.exp -= character.level * 100
        character.level += 1
        character.base_max_hp += LEVEL_UP_HP_GAIN
        character.base_attack += LEVEL_UP_ATTACK_GAIN
        character.hp = effective_max_hp(character)
        print(f"레벨업! Lv.{character.level} 달성! (기본 최대HP {character.base_max_hp}, 기본 공격력 {character.base_attack})")
        if character.level == BOSS_LEVEL_REQUIREMENT:
            print(f"\n불길한 기운이 감돈다... 이제 탐험하면 {BOSS_TEMPLATE['name']}과(와) 마주치게 됩니다!")


def use_potion(character: Character) -> None:
    owned = [(name, cnt) for name, cnt in character.potions.items() if cnt > 0]
    if not owned:
        print("보유한 포션이 없습니다.")
        return

    print("\n[보유 포션]")
    for i, (name, cnt) in enumerate(owned, start=1):
        print(f"{i}) {name} 포션 (HP+{POTION_HEAL[name]}) x{cnt}")
    choice = input("사용할 포션 번호 > ").strip()
    try:
        name, _ = owned[int(choice) - 1]
    except (ValueError, IndexError):
        print("잘못된 입력입니다.")
        return

    character.potions[name] -= 1
    heal = POTION_HEAL[name]
    character.hp = min(effective_max_hp(character), character.hp + heal)
    print(f"{name} 포션 사용! HP {heal} 회복 -> 현재 HP {character.hp}/{effective_max_hp(character)}")


def roll_stat(value_range: list, level: int, grade_mult: float, per_level: float) -> int:
    lo, hi = value_range
    growth = per_level * (level - 1)
    lo_val = (lo + growth) * grade_mult
    hi_val = (hi + growth) * grade_mult
    return max(1, round(random.uniform(lo_val, hi_val)))


def create_equipment(level: int) -> Equipment:
    part = random.choice(list(EQUIPMENT_PARTS.keys()))
    grade = random.choices(GRADE_NAMES, weights=GRADE_WEIGHTS, k=1)[0]
    grade_mult = GRADE_MULTIPLIER[grade]
    stat_ranges = EQUIPMENT_PARTS[part]
    attack = (
        roll_stat(stat_ranges["attack"], level, grade_mult, ATTACK_GROWTH_PER_LEVEL)
        if "attack" in stat_ranges
        else 0
    )
    hp = roll_stat(stat_ranges["hp"], level, grade_mult, HP_GROWTH_PER_LEVEL) if "hp" in stat_ranges else 0
    return Equipment(part=part, grade=grade, level=level, attack=attack, hp=hp)


def equip_item(character: Character, equipment: Equipment) -> None:
    slot = equipment.part
    current = character.equipped[slot]
    character.equipped[slot] = equipment
    if current:
        character.equipment_inventory.append(current)
        print(f"기존 장비를 인벤토리로 이동: {current}")
    character.hp = min(character.hp, effective_max_hp(character))
    print(f"장착 완료: {equipment}")


def offer_equip(character: Character, drop: Equipment) -> None:
    """드랍된 장비를 현재 장착 장비와 비교해서 보여주고 장착 여부를 묻는다."""
    print(f"\n장비 드랍: {drop}")
    current = character.equipped[drop.part]
    if current:
        print(f"현재 장착 중: {current}")
        print(f"변화: 공격력 {drop.attack - current.attack:+d}, HP {drop.hp - current.hp:+d}")
    else:
        print("현재 해당 부위는 비어 있습니다.")
    answer = input("장착하시겠습니까? (y/n) > ").strip().lower()
    if answer == "y":
        equip_item(character, drop)
    else:
        character.equipment_inventory.append(drop)
        print("인벤토리에 보관했습니다.")


def manage_equipment(character: Character) -> None:
    while True:
        print("\n--- 장비 관리 ---")
        for part, item in character.equipped.items():
            print(f"{part}: {item if item else '(없음)'}")
        print(f"\n총 공격력: {effective_attack(character)}  총 최대HP: {effective_max_hp(character)}")

        if not character.equipment_inventory:
            print("\n보유 중인 미착용 장비가 없습니다.")
            input("엔터를 누르면 돌아갑니다...")
            return

        print("\n[미착용 장비 목록] (판매는 상점에서 가능합니다)")
        for i, item in enumerate(character.equipment_inventory, start=1):
            print(f"{i}) {item}")

        choice = input("\n번호를 입력해 장착 (0: 뒤로가기) > ").strip()
        if choice == "0":
            return
        try:
            idx = int(choice) - 1
            item = character.equipment_inventory.pop(idx)
        except (ValueError, IndexError):
            print("잘못된 입력입니다.")
            continue
        equip_item(character, item)


def make_monster(template: dict, player_level: int) -> dict:
    base_hp = 30 + 12 * (player_level - 1)
    base_attack = 5 + 2.5 * (player_level - 1)
    power = template["power"]
    level_bonus = 1 + 0.15 * (player_level - 1)
    return {
        "name": template["name"],
        "hp": round(base_hp * power),
        "attack": round(base_attack * power),
        "exp": round(8 * power * level_bonus),
        "gold": round(10 * power * level_bonus),
    }


def battle(character: Character, monster: dict, is_boss: bool = False) -> BattleResult:
    monster_hp = monster["hp"]
    name = monster["name"]
    if is_boss:
        print(f"\n최후의 적, {name}이(가) 나타났다! (HP {monster_hp}, 공격력 {monster['attack']})")
    else:
        print(f"\n야생의 {name}이(가) 나타났다! (HP {monster_hp}, 공격력 {monster['attack']})")

    while True:
        atk = effective_attack(character)
        max_hp = effective_max_hp(character)
        print(f"\n[내 HP: {character.hp}/{max_hp}] [{name} HP: {monster_hp}]")
        choice = input("1) 공격  2) 포션 사용  3) 도망  > ").strip()

        if choice == "1":
            damage = max(1, random.randint(atk - 3, atk + 3))
            monster_hp -= damage
            print(f"{name}에게 {damage}의 피해를 입혔다.")
        elif choice == "2":
            use_potion(character)
        elif choice == "3":
            if random.random() < FLEE_FAIL_CHANCE:
                print("도망에 실패했다!")
                monster_damage = max(1, random.randint(monster["attack"] - 2, monster["attack"] + 2))
                character.hp -= monster_damage
                print(f"{name}의 반격! {monster_damage}의 피해를 입었다.")
                if character.hp <= 0:
                    print("\n쓰러졌습니다... 게임 오버.")
                    return "dead"
                continue
            print("도망쳤다!")
            return "alive"
        else:
            print("잘못된 입력입니다.")
            continue

        if monster_hp <= 0:
            print(f"\n{name}을(를) 물리쳤다!")
            if is_boss:
                print("\n=== GAME CLEAR ===")
                print(f"{character.name}님이 {name}을(를) 쓰러뜨리고 세상을 구했습니다!")
                return "cleared"

            character.exp += monster["exp"]
            character.gold += monster["gold"]
            print(f"경험치 +{monster['exp']}, 골드 +{monster['gold']}")
            level_up(character)

            drop = create_equipment(character.level)
            offer_equip(character, drop)
            return "alive"

        monster_damage = max(1, random.randint(monster["attack"] - 2, monster["attack"] + 2))
        character.hp -= monster_damage
        print(f"{name}의 반격! {monster_damage}의 피해를 입었다.")

        if character.hp <= 0:
            print("\n쓰러졌습니다... 게임 오버.")
            return "dead"


def explore(character: Character) -> BattleResult:
    if character.level >= BOSS_LEVEL_REQUIREMENT:
        monster = make_monster(BOSS_TEMPLATE, character.level)
        return battle(character, monster, is_boss=True)
    weights = [m["weight"] for m in MONSTERS]
    template = random.choices(MONSTERS, weights=weights, k=1)[0]
    monster = make_monster(template, character.level)
    return battle(character, monster)


def buy_potions(character: Character) -> None:
    print("\n[포션 구매]")
    for i, name in enumerate(POTION_NAMES, start=1):
        print(
            f"{i}) {name} 포션 - HP+{POTION_HEAL[name]} / {POTION_PRICE[name]}골드"
            f" (보유 {character.potions[name]}개)"
        )
    choice = input("구매할 포션 등급 번호 > ").strip()
    try:
        name = POTION_NAMES[int(choice) - 1]
    except (ValueError, IndexError):
        print("잘못된 입력입니다.")
        return

    qty_input = input(f"{name} 포션 구매 개수를 입력하세요 (1개 {POTION_PRICE[name]}골드) > ").strip()
    try:
        qty = int(qty_input)
    except ValueError:
        print("잘못된 입력입니다.")
        return
    if qty <= 0:
        print("1개 이상 입력하세요.")
        return
    cost = qty * POTION_PRICE[name]
    if character.gold < cost:
        print(f"골드가 부족합니다. (필요 골드: {cost}, 보유 골드: {character.gold})")
        return
    character.gold -= cost
    character.potions[name] += qty
    print(f"{name} 포션 {qty}개를 구매했습니다. (-{cost}골드)")


def sell_equipment(character: Character) -> None:
    if not character.equipment_inventory:
        print("판매할 미착용 장비가 없습니다.")
        return

    counts: dict[str, int] = {}
    total = 0
    for item in character.equipment_inventory:
        price = GRADE_SELL_PRICE[item.grade]
        total += price
        counts[item.grade] = counts.get(item.grade, 0) + 1

    print(f"\n[미착용 장비 일괄 판매] 총 {len(character.equipment_inventory)}개")
    for grade in GRADE_NAMES:
        if grade in counts:
            print(f"  {grade} {counts[grade]}개 x {GRADE_SELL_PRICE[grade]}골드")
    print(f"판매 시 획득 골드: {total}")

    answer = input("전부 판매하시겠습니까? (y/n) > ").strip().lower()
    if answer != "y":
        return
    character.gold += total
    character.equipment_inventory.clear()
    print(f"장비를 판매하여 {total}골드를 획득했습니다.")


def shop(character: Character) -> None:
    while True:
        print(f"\n[상점] 보유 골드: {character.gold}  포션: {sum(character.potions.values())}개")
        print("1) 포션 구매")
        print("2) 미착용 장비 일괄 판매")
        print("0) 나가기")
        choice = input("> ").strip()

        if choice == "0":
            return
        elif choice == "1":
            buy_potions(character)
        elif choice == "2":
            sell_equipment(character)
        else:
            print("잘못된 입력입니다.")


def main() -> None:
    print("=== 텍스트 RPG ===")
    start = input("1) 새 게임  2) 불러오기  > ").strip()
    character = load_game() if start == "2" else None
    if character is None:
        character = create_character()

    while True:
        print("\n1) 탐험하기  2) 상점  3) 상태 보기  4) 장비 관리  5) 저장하기  6) 종료")
        choice = input("> ").strip()

        if choice == "1":
            result = explore(character)
            if result in ("dead", "cleared"):
                break
        elif choice == "2":
            shop(character)
        elif choice == "3":
            show_status(character)
        elif choice == "4":
            manage_equipment(character)
        elif choice == "5":
            save_game(character)
        elif choice == "6":
            answer = input("종료 전 저장하시겠습니까? (y/n) > ").strip().lower()
            if answer == "y":
                save_game(character)
            print("게임을 종료합니다.")
            break
        else:
            print("잘못된 입력입니다.")


if __name__ == "__main__":
    main()
