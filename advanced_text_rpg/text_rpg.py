"""텍스트 기반 미니 RPG 게임 - 파이썬 입문용 실습 프로젝트"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field, asdict
from pathlib import Path

SAVE_FILE = Path("savegame.json")

# 장비 부위별로 가질 수 있는 스탯과, 레벨1·일반등급 기준 수치 범위
EQUIPMENT_PARTS = {
    "무기": {"attack": (3, 6)},
    "투구": {"attack": (1, 3), "hp": (6, 12)},
    "상의": {"hp": (14, 24)},
    "하의": {"hp": (14, 24)},
    "장갑": {"attack": (1, 3), "hp": (6, 12)},
    "신발": {"attack": (1, 3), "hp": (6, 12)},
}

# (등급명, 드랍 확률 가중치, 스탯 배율) - 가중치 합 100 = 고정 드랍 확률
GRADES = [
    ("일반", 70, 1.0),
    ("고급", 16, 1.6),
    ("희귀", 8, 2.4),
    ("영웅", 5, 3.6),
    ("전설", 1, 5.5),
]
GRADE_NAMES = [g[0] for g in GRADES]
GRADE_WEIGHTS = [g[1] for g in GRADES]
GRADE_MULTIPLIER = {g[0]: g[2] for g in GRADES}

ATTACK_GROWTH_PER_LEVEL = 0.6
HP_GROWTH_PER_LEVEL = 2.5


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


# (몬스터명, 출현 가중치, 전투력 배율) - 가중치 합 100 = 고정 출현 확률
# power가 클수록 플레이어 레벨 대비 훨씬 강해져서, 레벨업만으로는 못 이기고 장비가 필요해진다.
MONSTERS = [
    {"name": "슬라임", "weight": 10, "power": 1.0},
    {"name": "고블린", "weight": 15, "power": 1.4},
    {"name": "놀", "weight": 20, "power": 1.9},
    {"name": "오크", "weight": 20, "power": 2.6},
    {"name": "트롤", "weight": 10, "power": 3.6},
    {"name": "오거", "weight": 10, "power": 4.8},
    {"name": "마족", "weight": 10, "power": 6.4},
    {"name": "드래곤", "weight": 5, "power": 9.0},
]


@dataclass
class Character:
    name: str
    hp: int = 100
    base_max_hp: int = 100
    base_attack: int = 10
    level: int = 1
    exp: int = 0
    gold: int = 50
    potions: int = 2
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
    print(f"EXP: {character.exp}/{character.level * 100}  골드: {character.gold}  포션: {character.potions}개")
    print("\n[장착 장비]")
    for part, item in character.equipped.items():
        print(f"  {part}: {item if item else '(없음)'}")
    if character.equipment_inventory:
        print(f"\n미착용 장비 {len(character.equipment_inventory)}개 보유 중 (4번 메뉴에서 관리)")
    print("------------\n")


def level_up(character: Character) -> None:
    while character.exp >= character.level * 100:
        character.exp -= character.level * 100
        character.level += 1
        character.base_max_hp += 20
        character.base_attack += 5
        character.hp = effective_max_hp(character)
        print(f"레벨업! Lv.{character.level} 달성! (기본 최대HP {character.base_max_hp}, 기본 공격력 {character.base_attack})")


def use_potion(character: Character) -> None:
    if character.potions <= 0:
        print("포션이 없습니다.")
        return
    character.potions -= 1
    heal = 30
    character.hp = min(effective_max_hp(character), character.hp + heal)
    print(f"포션 사용! HP {heal} 회복 -> 현재 HP {character.hp}/{effective_max_hp(character)}")


def roll_stat(value_range: tuple, level: int, grade_mult: float, per_level: float) -> int:
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

        print("\n[미착용 장비 목록]")
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


def battle(character: Character, monster: dict) -> bool:
    monster_hp = monster["hp"]
    name = monster["name"]
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
            print("도망쳤다!")
            return True
        else:
            print("잘못된 입력입니다.")
            continue

        if monster_hp <= 0:
            print(f"\n{name}을(를) 물리쳤다!")
            character.exp += monster["exp"]
            character.gold += monster["gold"]
            print(f"경험치 +{monster['exp']}, 골드 +{monster['gold']}")
            level_up(character)

            drop = create_equipment(character.level)
            print(f"\n장비 드랍: {drop}")
            answer = input("바로 장착하시겠습니까? (y/n) > ").strip().lower()
            if answer == "y":
                equip_item(character, drop)
            else:
                character.equipment_inventory.append(drop)
                print("인벤토리에 보관했습니다.")
            return True

        monster_damage = max(1, random.randint(monster["attack"] - 2, monster["attack"] + 2))
        character.hp -= monster_damage
        print(f"{name}의 반격! {monster_damage}의 피해를 입었다.")

        if character.hp <= 0:
            print("\n쓰러졌습니다... 게임 오버.")
            return False


def explore(character: Character) -> bool:
    weights = [m["weight"] for m in MONSTERS]
    template = random.choices(MONSTERS, weights=weights, k=1)[0]
    monster = make_monster(template, character.level)
    return battle(character, monster)


def shop(character: Character) -> None:
    print(f"\n[상점] 보유 골드: {character.gold}")
    print("포션 1개 = 10골드")
    choice = input("포션을 구매하시겠습니까? (y/n) > ").strip().lower()
    if choice != "y":
        return
    if character.gold < 10:
        print("골드가 부족합니다.")
        return
    character.gold -= 10
    character.potions += 1
    print("포션을 구매했습니다.")


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
            alive = explore(character)
            if not alive:
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
            print("게임을 종료합니다.")
            break
        else:
            print("잘못된 입력입니다.")


if __name__ == "__main__":
    main()
