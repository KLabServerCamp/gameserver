class ValidScore:
    normal_max: int
    hard_max: int
    max_notes_normal: int
    max_notes_hard: int

    def __init__(self, normal_max, hard_max, max_notes_normal, max_notes_hard) -> None:
        self.normal_max = normal_max
        self.hard_max = hard_max
        self.max_notes_normal = max_notes_normal
        self.max_notes_hard = max_notes_hard


# 1003: 歓喜の歌
# 1000: iRodoRi
# 1001: コタエサガシ
# 1002: chromatic
# 1501: cosmic sunset
# 1500: cosmic flyer
# 1004: wings of condemnation
valid_scores = {
    1003: ValidScore(
        normal_max=10401434, max_notes_normal=147, hard_max=10484888, max_notes_hard=367
    ),
    1000: ValidScore(
        normal_max=10366400, max_notes_normal=131, hard_max=10476664, max_notes_hard=344
    ),
    1001: ValidScore(
        normal_max=10440403, max_notes_normal=259, hard_max=10490647, max_notes_hard=536
    ),
    1002: ValidScore(
        normal_max=10181870, max_notes_normal=253, hard_max=10617467, max_notes_hard=536
    ),
    1501: ValidScore(
        normal_max=10335958, max_notes_normal=125, hard_max=10533598, max_notes_hard=506
    ),
    1500: ValidScore(
        normal_max=10220874, max_notes_normal=163, hard_max=10375764, max_notes_hard=700
    ),
    1004: ValidScore(
        normal_max=10410114, max_notes_normal=405, hard_max=10401964, max_notes_hard=632
    ),
}
