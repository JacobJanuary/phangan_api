"""Static name dictionaries for fast first-pass gender/language detection.

Kept as a frozen module to make swap-out / extension trivial.
"""

from __future__ import annotations

# Russian female names (nominative + common short forms).
FEMALE_NAMES_RU: frozenset[str] = frozenset({
    "александра", "алёна", "алена", "алина", "алиса", "алла", "альбина",
    "анастасия", "настя", "ангелина", "анжела", "анна", "аня",
    "валентина", "валерия", "лера", "варвара", "вера", "вероника", "виктория", "вика",
    "галина", "дарья", "даша", "диана", "евгения", "женя",
    "екатерина", "катя", "елена", "лена", "елизавета", "лиза",
    "жанна", "злата", "зоя", "инна", "ирина", "ира",
    "карина", "кира", "кристина", "ксения", "ксюша",
    "лариса", "лидия", "лилия", "любовь", "люба", "людмила", "люда",
    "маргарита", "рита", "марина", "мария", "маша",
    "надежда", "надя", "наталья", "наталия", "наташа",
    "нина", "оксана", "олеся", "ольга", "оля",
    "полина", "регина", "роза", "светлана", "света",
    "снежана", "софья", "софия", "соня",
    "тамара", "татьяна", "таня", "ульяна",
    "элина", "эльвира", "юлия", "юля", "яна", "асель",
})

# Russian male names (nominative + common short forms).
MALE_NAMES_RU: frozenset[str] = frozenset({
    "александр", "саша", "алексей", "лёша", "леша", "анатолий",
    "андрей", "антон", "аркадий", "артём", "артем", "артур",
    "богдан", "борис", "вадим", "валентин", "валерий",
    "василий", "виктор", "виталий", "владимир", "вова", "владислав", "влад",
    "вячеслав", "геннадий", "георгий", "глеб", "григорий",
    "даниил", "данил", "денис", "дмитрий", "дима",
    "евгений", "егор", "иван", "ваня", "игорь",
    "илья", "кирилл", "константин", "костя",
    "леонид", "максим", "макс", "марк", "матвей", "михаил", "миша",
    "никита", "николай", "коля", "олег",
    "павел", "паша", "пётр", "петр", "роман", "рома",
    "руслан", "сергей", "серёжа", "сережа",
    "станислав", "стас", "степан", "тимофей", "тимур",
    "фёдор", "федор", "филипп", "эдуард", "юрий", "юра", "ярослав",
})

# Common international names.
FEMALE_NAMES_INT: frozenset[str] = frozenset({
    "anna", "maria", "julia", "natalia", "natalya", "natasha", "nina",
    "olga", "elena", "ekaterina", "dasha", "polina", "anastasia",
    "helen", "diana", "victoria", "marina", "sophia", "sofia",
    "alice", "emma", "olivia", "emily", "sarah", "jessica",
    "jennifer", "ashley", "amanda", "rachel", "megan", "lisa",
    "michelle", "laura", "stephanie", "nicole",
})

MALE_NAMES_INT: frozenset[str] = frozenset({
    "alex", "alexander", "alexey", "sergei", "dmitry", "nikolai",
    "roman", "boris", "igor", "anton", "leon", "leo",
    "mark", "max", "maksim", "jacob", "james", "john", "robert",
    "michael", "david", "daniel", "matthew", "andrew", "joseph",
    "william", "richard", "thomas", "christopher", "brian", "kevin",
    "nick", "peter", "paul", "george", "denis", "dinar",
    "fedor", "jaroslav", "konstantin", "ruslan", "yuri", "danny",
})

# Latin transliterations of distinctly Russian names — used for language hint.
RU_LATIN_NAMES: frozenset[str] = frozenset({
    "polina", "dasha", "natalia", "natalya", "natasha", "sergei",
    "dmitry", "nikolai", "alexey", "ekaterina", "anastasia",
    "ruslan", "yuri", "maksim", "fedor", "jaroslav", "konstantin",
    "dinar", "marina", "olga", "elena", "boris", "igor", "anton",
    "roman", "denis",
})
