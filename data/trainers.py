# data/trainers.py
# Viridian Forest trainer roster (user-confirmed for this randomized romhack)
# Each trainer is a list of levels. Species are assigned randomly per seed.

from dataclasses import dataclass

@dataclass(frozen=True)
class TrainerSlot:
    trainer: str
    slot: int        # 0-indexed position in trainer's party
    level: int

# Trainers in battle order: Rick -> Anthony -> Charlie -> Doug -> Sammy
VIRIDIAN_FOREST_TRAINERS: list[TrainerSlot] = [
    # Rick: two Lv 9s
    TrainerSlot("Rick",    0, 9),
    TrainerSlot("Rick",    1, 9),

    # Anthony: leads with Lv 11, then Lv 12
    TrainerSlot("Anthony", 0, 11),
    TrainerSlot("Anthony", 1, 12),

    # Charlie: three Lv 11s
    TrainerSlot("Charlie", 0, 11),
    TrainerSlot("Charlie", 1, 11),
    TrainerSlot("Charlie", 2, 11),

    # Doug: three Lv 11s
    TrainerSlot("Doug",    0, 11),
    TrainerSlot("Doug",    1, 11),
    TrainerSlot("Doug",    2, 11),

    # Sammy: one Lv 14
    TrainerSlot("Sammy",   0, 14),
]

# Group by trainer name for per-trainer reporting
TRAINER_NAMES = ["Rick", "Anthony", "Charlie", "Doug", "Sammy"]
