"""How a lesson is formed (ADR-061).

Every lesson Adle writes follows the same few rules, whatever it teaches: something to look
at first, the idea worked out in it, and only then the rule, in the subject's own terms.
Those are the axioms. A subject then needs things the others do not: mathematics a picture
and an example in numbers before its equation, a language its rule shown inside real
sentences, chemistry an experiment before its particles and its equation. Each subject's
needs are listed here, explicitly, one subject at a time.

This module is the one place they are written down. Each rule is kept twice, side by side:
as one short line a learner can read ("How lessons are formed", in a course), and as the
brief the writer of a lesson is given (``prompts.lesson_request``). What the core can check
or mend by itself it does where the lesson is put together (``generation/slides.py``
moves a rule that a slide shows before its case, ADR-050).

Pure: no database, no framework. A subject's key is stored with a course and never shown;
its name is.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from adle_core.lessons.ir import STRATEGIES


@dataclass(frozen=True, slots=True)
class Axiom:
    """One rule every lesson follows."""

    key: str
    #: For the learner: one short sentence.
    rule: str
    #: For the writer of a lesson.
    brief: str


#: The rules of every lesson, in the order a lesson obeys them.
AXIOMS: tuple[Axiom, ...] = (
    Axiom(
        "case_first",
        "Each part starts with something to look at: an example, a case, an experiment.",
        "Example first, theory after, always. The learner watches a case happen and works "
        "it out with you; only then is the general rule said, as a summary of what they "
        "just saw.",
    ),
    Axiom(
        "worked_in_the_case",
        "The idea is worked out in that example, step by step.",
        "So a part that teaches goes in this order. Its narration opens on the case itself "
        '("Toss a coin twice."), never on a definition ("A sample space is..."). Its '
        "visual begins with the case alone on the stage: the objects, small numbers, a real "
        "sentence, what is in the glass; no rule, no definition and no formula yet. Its "
        "next steps act on that case as you speak (color, move, highlight, count or change "
        'with "set"), so the idea is seen happening.',
    ),
    Axiom(
        "rule_after",
        "The rule comes after, made from what you saw.",
        "Only then comes the rule: the definition, the law, the formula, in the subject's "
        "own terms and notation, tied to the picture by the same colors and the same "
        "numbers. A formula comes first in the case's own numbers, brought out of the "
        'picture with "from", each number in the color of what it counts; last, if the '
        'part states a general rule, "transform" those numbers into its symbols.',
    ),
    Axiom(
        "named_after_seen",
        "A name comes after the thing it names.",
        "A name or a definition comes after two or three instances of it: show the "
        "instances, point at what they share, then name it.",
    ),
    Axiom(
        "one_idea",
        "One idea at a time, each built on the last. A question follows.",
        "The lesson moves the same way: its first part is a concrete case with no "
        "definition in it; the general statement comes in a later part, built from the "
        "cases before it; then a new case shows what changes and what stays the same. One "
        "idea a part.",
    ),
    Axiom(
        "picture_carries",
        "Every part that teaches has a picture, with few words on it.",
        "The picture carries the idea. Every part that teaches has a visual that changes "
        "as you speak, and most of its steps change what is already on the stage rather "
        "than add something new. 3 to 6 steps in a visual, four to eight elements on the "
        "stage. Words on the stage are short, labels rather than paragraphs: the narration "
        "says the rest.",
    ),
    Axiom(
        "child_could_follow",
        "Explained so that a child could follow, and nothing skipped.",
        "Explain as you would to a bright child who has met only what the lesson builds on: "
        "every step said, never left for the learner to guess; every new word explained the "
        "first time it is used; an everyday example or comparison wherever it helps; the "
        "intuition before the formal statement. Take as many parts as the concept needs, and "
        "never hurry.",
    ),
    Axiom(
        "summed_up_along_the_way",
        "Along the way, a short summary of what you have learned so far.",
        "After every three or four parts of new material, a summary part says in two or "
        "three beats what has been learned so far and how it fits together, its picture "
        "bringing back what was shown; and the lesson ends with one of the whole of it.",
    ),
    Axiom(
        "beyond_the_examples",
        "From the examples to the general idea, and where it holds.",
        "Before the end, generalize: what holds beyond the examples worked and why, where it "
        "stops holding, and one new case that shows it.",
    ),
    Axiom(
        "light_touch",
        "Now and then, a light moment or a fun fact, never in the way.",
        "Write every word as the teacher described above would say it, so that their manner "
        "is heard in every part. Two or three times in a lesson, and never in more than one "
        "part of every four, a light, witty moment or a fun fact that belongs to the topic "
        "and is true, as that teacher allows (one who never jokes, or tells no fun facts, "
        "leaves that out): never in a question, never at the learner's expense, and never in "
        "place of a step of the teaching.",
    ),
    Axiom(
        "nothing_made_up",
        "Nothing is made up. Your materials come first.",
        "Use the lesson's own numbers, names and examples in the visuals and in the "
        "questions, and the learner's terms where they gave materials. A fact, a date, a "
        "quotation or a figure you are not sure of is left out, never invented.",
    ),
)

#: What the writer is told last: where to spend its care.
_FORGIVEN = (
    "Adle forgives a visual's small slips: what it cannot draw it leaves out, and it fits "
    "the brackets to the steps. Spend your thought on the teaching, not on checking the "
    "scripts."
)


@dataclass(frozen=True, slots=True)
class Subject:
    """What one subject needs of a lesson that the others do not."""

    key: str
    #: As a learner reads it: "Chemistry".
    name: str
    #: For the learner: how a lesson of it goes, as three short steps.
    steps: tuple[str, str, str]
    #: For the writer: the subject's own rules, one a line.
    brief: tuple[str, ...]
    #: The ways of teaching that suit it, in the order they are tried.
    strategies: tuple[str, ...]
    #: Which example part the writer is shown (``generation/examples.py``).
    example: str
    #: Words that say a course is of this subject, each matched as a whole word or its
    #: plural; one ending in * also as the beginning of a word ("probabilit*").
    #: Written as one line, a comma between them. A ~ before one says it counts for half: a
    #: word that is often about something else ("French" in "The French Revolution").
    signs: str = ""


GENERAL = "general"

_ALL_WAYS = ("visual", "worked_example", "analogy", "mathematical", "computational", "socratic")
_WORDY_WAYS = ("visual", "analogy", "worked_example", "socratic")

SUBJECTS: dict[str, Subject] = {
    subject.key: subject
    for subject in (
        Subject(
            key="mathematics",
            name="Mathematics",
            steps=(
                "A picture or a count, with small numbers",
                "One example worked in those numbers",
                "The equation, made from the example",
            ),
            brief=(
                "The case is a picture or a count with small numbers: a quantity shown as a "
                'length, an area, a count, a slope or a motion ("grid", "set", '
                '"number_line", "axes" with a "curve", "bars", coins and dice).',
                "Work one example in numbers on the stage before any symbol appears; let a "
                '"param" or a "set" show how changing one thing changes another.',
                "Then the equation: in the example's own numbers first, out of the picture "
                'with "from"; then the same line in symbols. Derive, one justified step at '
                "a time; never state a formula and ask the learner to trust it.",
                'A "worked_example" solves one problem line by line, a step of the visual '
                "for each line.",
                "Numbers are small and come out exactly. Where there is a number to find, "
                'ask for it ("numeric"); wrong options are slips a learner really makes: a '
                "sign, an order of steps, a rule used where it does not hold.",
            ),
            strategies=(
                "visual",
                "worked_example",
                "mathematical",
                "analogy",
                "computational",
                "socratic",
            ),
            example="area",
            signs=(
                "mathematic*, math, algebra*, calculus, geometr*, trigonometr*, "
                "probabilit*, statistic*, arithmetic, equation, derivative, integral, "
                "fraction, number theory, matrix, matrices, polynomial, logarithm*, theorem, "
                "combinatorics, differential equations, set theory, topology, quadratic*, "
                "counting, percentage, ratio, decimal, multiplication, division, exponent, "
                "vector, complex numbers, sequences and series, proofs, integers, "
                "functions and graphs"
            ),
        ),
        Subject(
            key="physics",
            name="Physics",
            steps=(
                "Something that happens: a push, a fall, a wave",
                "What changes with what, measured",
                "The law, with its units",
            ),
            brief=(
                "The case is something that happens: a thing dropped, pushed, heated or "
                'swung, a wave, a circuit switched on. Show it with shapes, with an "arrow" '
                'out of a thing ("toward" a side) for each force on it and a "vector" for a '
                'velocity, and let it move ("move", a point on a "number_line", a "param").',
                'Then measure it: a few readings in a "table", or a "curve" on "axes" whose '
                'labels carry the units; a "param" shows what changes with what.',
                "Then the law: with the case's own numbers and units first, then in "
                "symbols. Say what each symbol stands for and its unit, and where the law "
                "stops holding.",
                'A "worked_example" carries its units on every line.',
                "Ask what will happen before asking for a number; a numeric answer has its "
                '"unit". Wrong options are the usual wrong pictures: heavier falls faster, '
                "a force is needed to keep moving.",
            ),
            strategies=(
                "visual",
                "worked_example",
                "analogy",
                "mathematical",
                "socratic",
                "computational",
            ),
            example="falling",
            signs=(
                "physics, mechanics, kinematics, thermodynamic*, electromagneti*, "
                "electricity, magnetism, optics, quantum, relativity, newton*, momentum, "
                "velocity, acceleration, gravity, gravitation, circuit, friction, lever, "
                "pulley, simple machines, torque, ~pressure, force and motion, "
                "laws of motion, forces, waves, nuclear physics, electric current, "
                "work and energy, reflection, refraction"
            ),
        ),
        Subject(
            key="chemistry",
            name="Chemistry",
            steps=(
                "An experiment: what is mixed, and what you see",
                "What the particles are doing",
                "The equation, balanced",
            ),
            brief=(
                "The case is an experiment: what is put together and what is seen. Show it "
                'with a "vessel" (what is in it, its color), and change it as the narration '
                'says what is observed: a new color ("color"), bubbles, a solid at the '
                'bottom, heat ("set").',
                "Then what the particles do: the substances that matter drawn as "
                '"molecule" elements (which atoms, which bonds), or counted in a "table".',
                'Then the equation, balanced, as a "math" element, with \\mathrm{...} round '
                "each formula and \\rightarrow between the sides, each substance in the "
                "color it had in the picture. Give state symbols and conditions where they "
                "matter.",
                "A substance is named after it has been seen, and its formula comes after "
                "its name. The narration says a substance by its name (hydrochloric acid), "
                "never by its formula or a state symbol.",
                "Say when an experiment needs a laboratory and a teacher. Never present "
                "one that can hurt as something to try.",
                "Ask what will be seen, which substance forms, or for a count that the "
                "equation gives; wrong options are real confusions (atoms lost, charges "
                "ignored).",
            ),
            strategies=("visual", "worked_example", "analogy", "socratic", "mathematical"),
            example="experiment",
            signs=(
                "chemistry, chemical*, molecule, molecular, periodic table, acids and bases, "
                "acid, compound, carbon, covalent, ionic, stoichiometry, oxidation, redox, "
                "titration, hydrocarbon, polymer, electrolysis, isotope, atom, atomic, "
                "mole concept, bonding, organic chemistry, metals and non-metals, salts, "
                "alkane, alcohols, corrosion, reactions"
            ),
        ),
        Subject(
            key="biology",
            name="Biology",
            steps=(
                "One living thing, or one part of it, drawn and named",
                "What each part does, step by step",
                "The term and the general idea",
            ),
            brief=(
                "The case is one particular living thing, organ, cell or event (one "
                'heartbeat, one leaf in the light). Show its parts as shapes with a "label" '
                'each, or its stages as "nodes" in a row or a circle.',
                "Then follow one thing through it, step by step (a drop of blood, a "
                "molecule of sugar, a signal), highlighting each part as it does its work: "
                "what it is, then what it does.",
                "Then the term and the general statement. A name arrives with its part on "
                "the stage, never as a list of terms to learn.",
                'Set two cases side by side in a "table" to show what differs.',
                "Ask for the order of the stages, for what would happen if one part "
                "failed, and for the same idea in another living thing.",
            ),
            strategies=_WORDY_WAYS,
            example="leaf",
            signs=(
                "biology, biological, cell, genetic*, dna, evolution, ecology, anatomy, "
                "physiology, photosynthesis, respiration, organism, protein, enzyme, "
                "bacteria, virus, immune, neuron, heart, plant, animal, species, mitosis, "
                "meiosis, ecosystem, botany, zoology, microbiology, digestion, hormone, "
                "medicine, nutrition, life processes, reproduction, heredity, "
                "nervous system, blood"
            ),
        ),
        Subject(
            key="earth_science",
            name="Earth and space",
            steps=(
                "One place or one event",
                "The process, step by step",
                "The pattern, and where else it shows",
            ),
            brief=(
                "The case is one place or one event: one river, one eruption, one day of "
                "weather, one orbit. Show it as a simple diagram (shapes, arrows, a "
                '"label" each), a cycle ("nodes" in a circle), or measurements as "bars" or '
                'on "axes".',
                "Then the process, step by step: what moves, what causes what (arrows), "
                'and over how long (a "timeline" for long spans).',
                "Then the general pattern and its name; then a second place where it shows "
                "differently.",
                "Give sizes, distances and times as real figures with their units, rounded "
                "as a person would say them.",
                "Ask what happens next, for the order of the steps, and for the same "
                "process somewhere else.",
            ),
            strategies=_WORDY_WAYS,
            example="water_cycle",
            signs=(
                "geography, geology, earth science, climate, weather, plate tectonics, "
                "volcano*, earthquake, river, ocean, atmosphere, astronomy, planet, "
                "solar system, galaxy, galaxies, mineral, erosion, water cycle, "
                "environmental, continent, rocks, stars, universe, natural resources, "
                "landform, ~environment"
            ),
        ),
        Subject(
            key="computer_science",
            name="Computer science",
            steps=(
                "One small input, run by hand",
                "The code, line by line beside it",
                "The idea behind it, and what it costs",
            ),
            brief=(
                "The case is one small input run by hand: a list of five numbers, one "
                'word, three records. Show the data ("grid" for a list, "nodes" for linked '
                'things and trees, "number" for a variable) and change it step by step with '
                '"set", "color" and "move", the way a program would.',
                'Then the code: a "code" element of a few lines, the line being run '
                "highlighted while the data changes beside it. Real code in one language "
                "(the course's own; Python if it has none) that would run as written.",
                "Then the general idea: what stays true at every step, the rule, or the "
                "cost, in words; as a formula only if it is needed.",
                "Ask for a trace (what it prints, the next state), for the bug in a few "
                "lines, and for the same idea on other data; wrong options are real slips: "
                "off by one, the wrong order, a value not updated.",
            ),
            strategies=(
                "visual",
                "worked_example",
                "computational",
                "analogy",
                "socratic",
                "mathematical",
            ),
            example="trace",
            signs=(
                "computer science, programming, python, javascript, java, algorithm, "
                "data structure, coding, software, database, sql, machine learning, "
                "neural network, compiler, operating system, recursion, sorting, "
                "linked list, binary, web development, html, api, cybersecurity, "
                "cryptography, artificial intelligence, deep learning, typescript, "
                "data science, computing, computer, ~code, language model, "
                "large language model"
            ),
        ),
        Subject(
            key="language",
            name="Language",
            steps=(
                "Real sentences first",
                "The words that matter, marked and changed",
                "The rule in one line, then where it bends",
            ),
            brief=(
                "Everything is taught inside real sentences. The case is one or two "
                'sentences a person would really say or write ("words"); the rule is never '
                "stated before they have been read.",
                'Work on the sentence itself: "color" and "label" the words that carry the '
                'idea, set a "brace" or an "outline" on a phrase, "transform" or "set" the '
                "sentence into another to show the rule at work, and put a wrong use "
                "beside the right one and say exactly why it is wrong.",
                'Then the rule in one short line (a "box"), in plain words, once at least '
                "two sentences have shown it; then a sentence where the rule bends or does "
                "not apply.",
                "For a language being learned: the sentence in that language with its "
                "meaning beneath it, the pattern marked in both.",
                "Ask for the right form in a new sentence (choices that are whole "
                'sentences, or a "short_answer" of a word or two), for words put in order '
                '("ordering"), and for a sentence to be mended.',
            ),
            strategies=("worked_example", "visual", "analogy", "socratic"),
            example="sentence",
            signs=(
                "grammar, ~english, vocabulary, ~writing, essay, punctuation, spelling, "
                "tense, verb, noun, adjective, sentence, passive voice, ~spanish, ~french, "
                "~german, ~hindi, ~japanese, ~chinese, ~mandarin, ~latin, language, "
                "pronunciation, composition, linguistics, conjugation, preposition, clause, "
                "~italian, ~korean, ~arabic, ~portuguese, ~russian, proofreading"
            ),
        ),
        Subject(
            key="literature",
            name="Literature",
            steps=(
                "A short passage, quoted",
                "The words that do the work, and what they do",
                "The reading, with its evidence",
            ),
            brief=(
                "The case is a short passage. Quote it exactly from the learner's own "
                "materials when there are any; otherwise a line or two of a work old "
                "enough to be quoted freely, or a line written for the lesson and said to "
                'be. Put it on the stage as "words", a line of the passage to an element.',
                "Read it closely: highlight the words that do the work (an image, a sound, "
                "a turn), name the device only after it has been noticed, and say what it "
                "does to a reader.",
                "Then the term or the reading, tied to the words pointed at; where good "
                "readers differ, show two readings and what each rests on.",
                "Never invent a quotation, an event of a plot, or what an author said.",
                "Ask what a phrase is doing, for the words that support a reading, and for "
                'a reading explained ("explanation", with a rubric).',
            ),
            strategies=("visual", "socratic", "analogy", "worked_example"),
            example="passage",
            signs=(
                "literature, poem, poetry, novel, shakespeare*, drama, short story, "
                "short stories, fiction, literary, metaphor, sonnet, prose, narrative, "
                "hamlet, macbeth, tragedy"
            ),
        ),
        Subject(
            key="history",
            name="History",
            steps=(
                "One moment: a person, a place, a date",
                "What led to it, and what came of it",
                "The claim, and how we know",
            ),
            brief=(
                "The case is one moment: a person, a place, a date, a decision, or a "
                "source (a few words quoted from the learner's materials, if they gave "
                'any). Put it on a "timeline" with the two or three events around it.',
                'Then causes and effects, as "nodes" joined by arrows: what led to it, '
                'what came of it; two sides or two periods side by side in a "table".',
                "Then the general claim a historian would make, said as a claim with its "
                "evidence; where historians disagree, give both views fairly.",
                "A date, a name or a number is right or it is left out. No invented quotations.",
                'Ask for events in order ("ordering"), for a cause or an effect, and for '
                'why something happened ("explanation").',
            ),
            strategies=_WORDY_WAYS,
            example="timeline",
            signs=(
                "history, revolution, war, empire, ancient, medieval, civilization, dynasty, "
                "colonial*, world war, renaissance, reformation, cold war, "
                "industrial revolution, historical, archaeology, nationalism, civil rights, "
                "the rise of, the fall of"
            ),
        ),
        Subject(
            key="economics",
            name="Economics and business",
            steps=(
                "One small situation, with numbers",
                "Change one thing and watch the rest",
                "The principle, and what it assumes",
            ),
            brief=(
                "The case is one small situation with numbers: one shop, one buyer, one "
                'price change, one loan. Put the numbers in a "table" or as "bars".',
                'Then change one thing and watch the others ("set", a "param"); a "curve" '
                'on "axes" comes from those numbers, its axes named, with their units.',
                "Then the principle, with what it assumes; then a case where the assumption fails.",
                'Ask for a figure worked from a small table ("numeric"), for which way '
                "something moves, and for the principle in another market.",
            ),
            strategies=("worked_example", "visual", "analogy", "mathematical", "socratic"),
            example="demand",
            signs=(
                "economics, economy, microeconomics, macroeconomics, supply and demand, "
                "market, marketing, finance, financial, accounting, business, investment, "
                "investing, inflation, gdp, trade, money, banking, entrepreneurship, stocks, "
                "interest rate, budget, taxes, demand, profit"
            ),
        ),
        Subject(
            key="social_science",
            name="Society and mind",
            steps=(
                "One case, study or thought experiment",
                "The idea that explains it",
                "The evidence, and its limits",
            ),
            brief=(
                "The case is one concrete scenario, study or thought experiment: who did "
                'what, and what happened. Show the people or groups as shapes or "nodes", '
                'and a result as "bars" or a "table".',
                "Then the idea that explains it, and the distinction it rests on (a "
                '"table" of two columns: what it is, what it is not).',
                "Then the general statement, the evidence for it and its limits. For an "
                'argument: its steps as "nodes" in a column, from what is assumed to what '
                "follows, and the strongest objection.",
                "Describe findings and positions fairly. No invented studies, names or "
                "numbers; on a contested question give the main views, each as its "
                "holders would put it.",
                'Ask which idea a new case shows, and for an explanation ("explanation").',
            ),
            strategies=("analogy", "visual", "socratic", "worked_example"),
            example="common_cause",
            signs=(
                "psychology, sociology, politics, political, government, civics, "
                "constitutional law, criminal law, legal, philosophy, ethics, anthropology, "
                "constitution, democracy, society, cognitive, behavior, citizenship, "
                "international relations, critical thinking, human rights, social*"
            ),
        ),
        Subject(
            key="arts",
            name="Arts and music",
            steps=(
                "One work or one pattern, described closely",
                "What repeats, what contrasts, what leads",
                "The term, then the same idea elsewhere",
            ),
            brief=(
                "The case is one work or one small pattern, described exactly: a rhythm "
                "counted out, the notes of a chord, a palette, the layout of a picture as "
                "shapes on the stage.",
                "Work on it: mark what repeats, what contrasts, what leads the eye or the "
                'ear (a "grid" for beats, shapes and colors for form).',
                "Then the term and the principle; then the same idea in a second work.",
                "Adle cannot show a real work or play a sound: describe it in the "
                "narration, and draw only simple diagrams.",
                "Ask for the idea found in a case described, for an order, and for an explanation.",
            ),
            strategies=_WORDY_WAYS,
            example="meter",
            signs=(
                "music, ~art, painting, drawing, graphic design, film, photography, "
                "architecture, harmony, chord, rhythm, melody, color theory, typography, "
                "sculpture, dance, theater, theatre, music theory, art history"
            ),
        ),
        Subject(
            key=GENERAL,
            name="General",
            steps=(
                "One example you can picture",
                "The idea worked out in it",
                "The rule, made from the example",
            ),
            brief=(
                "Mathematics and science: show a quantity as a length, an area, a count, a "
                'slope or a motion; let a "param" or a "set" show how changing one thing '
                "changes another; derive the formula from the picture, one step at a time. "
                'An experiment is shown in a "vessel", a substance as a "molecule".',
                'Language and writing: show real sentences ("words"), color and label the '
                "words that carry the idea, turn one sentence into another to show a rule "
                "at work, and set a right use beside a wrong one.",
                'Programming: one small input run by hand, then the "code", the line being '
                "run highlighted.",
                "History, the life sciences, economics and the rest: a concrete case first "
                '(a person, a place, a date, a number); then dates on a "timeline", causes '
                'and effects or the stages of a process as "nodes", comparisons as "bars" '
                'or a "table".',
            ),
            strategies=_ALL_WAYS,
            example="area",
        ),
    )
}

#: The subjects a course may be given, in the order a learner is offered them.
SUBJECT_KEYS: tuple[str, ...] = tuple(SUBJECTS)


def subject(key: str | None) -> Subject:
    """The subject of that key; the general one for a key there is not."""
    return SUBJECTS.get(key or GENERAL, SUBJECTS[GENERAL])


def subject_key(value: object) -> str | None:
    """A subject's key from what was written for it ("Computer Science", "earth-science"),
    or None when it names none. A model, and a file from elsewhere, may write it loosely."""
    if not isinstance(value, str):
        return None
    written = "_".join(re.sub(r"[^a-z]+", " ", value.lower()).split())
    if written in SUBJECTS:
        return written
    names = {"_".join(item.name.lower().split()): item.key for item in SUBJECTS.values()}
    aliases = {
        "math": "mathematics",
        "science": GENERAL,
        "cs": "computer_science",
        "programming": "computer_science",
        "computing": "computer_science",
        "geography": "earth_science",
        "earth_and_space_science": "earth_science",
        "english": "language",
        "grammar": "language",
        "business": "economics",
        "economics_and_business": "economics",
        "psychology": "social_science",
        "social_studies": "social_science",
        "philosophy": "social_science",
        "art": "arts",
        "music": "arts",
        "other": GENERAL,
    }
    # And a name written with an s it does not have here: "languages", "social sciences".
    single = written.removesuffix("s")
    return (
        names.get(written)
        or aliases.get(written)
        or (single if single in SUBJECTS else None)
        or aliases.get(single)
    )


def ways_for(key: str | None) -> tuple[str, ...]:
    """The ways of teaching that suit a subject, in the order they are tried."""
    return tuple(way for way in subject(key).strategies if way in STRATEGIES)


def _sign_pattern(sign: str) -> tuple[re.Pattern[str], float]:
    # A whole word or its plural; with a star, the beginning of any word. And what finding
    # it counts for.
    weight = 0.5 if sign.startswith("~") else 1.0
    sign = sign.lstrip("~")
    stem = sign.endswith("*")
    words = [re.escape(word) for word in sign.rstrip("*").split()]
    last = words[-1] + (r"\w*" if stem else r"(?:s|es)?")
    return re.compile(r"(?<!\w)" + r"\s+".join([*words[:-1], last]) + r"(?!\w)"), weight


_SIGNS: dict[str, tuple[tuple[re.Pattern[str], float], ...]] = {
    item.key: tuple(_sign_pattern(sign) for sign in item.signs.split(", ") if sign)
    for item in SUBJECTS.values()
}


def guess(name: str | None, *more: str | None) -> str:
    """The subject a course seems to be of, from its name and what else it says of itself;
    the general one when nothing says, or when two subjects are as likely as each other.
    A word in the name counts twice a word elsewhere: "The French Revolution" is history,
    whatever "pressures" its description speaks of.

    A guess, made without asking anyone: the list of a course's concepts, when a model
    writes it, says the subject better (``prompts.curriculum_request``), and the learner's
    own choice stands over both.
    """

    def lowered(texts: tuple[str | None, ...]) -> str:
        return " ".join(" ".join(str(text).lower().split()) for text in texts if text)

    title, rest = lowered((name,)), lowered(more)
    if not title and not rest:
        return GENERAL
    scores = {
        key: sum(
            weight * (2 if pattern.search(title) else 1)
            for pattern, weight in patterns
            if pattern.search(title) or pattern.search(rest)
        )
        for key, patterns in _SIGNS.items()
    }
    best = max(scores.values(), default=0.0)
    if best == 0:
        return GENERAL
    leaders = [key for key, score in scores.items() if score == best]
    return leaders[0] if len(leaders) == 1 else GENERAL


def teaching_brief(key: str | None) -> str:
    """How to teach a lesson of a subject, for its writer: the rules of every lesson, then
    what this subject needs besides."""
    chosen = subject(key)
    lines = ["How every lesson is formed (this is what makes it good):"]
    lines += [f"- {axiom.brief}" for axiom in AXIOMS]
    if chosen.key == GENERAL:
        lines.append("")
        lines.append("What each kind of subject needs besides:")
    else:
        lines.append("")
        lines.append(
            f"This course is {chosen.name.lower()}. What a lesson of it needs besides, in "
            "this order:"
        )
    lines += [f"- {line}" for line in chosen.brief]
    lines.append(f"- {_FORGIVEN}")
    return _indented("\n".join(lines))


def _indented(text: str) -> str:
    """Lines wrapped at about 90 characters, a bullet's later lines set in under it."""
    wrapped: list[str] = []
    for line in text.split("\n"):
        words = line.split()
        current = ""
        for word in words:
            if current and len(current) + 1 + len(word) > 90:
                wrapped.append(current)
                current = "  " + word
            else:
                current = f"{current} {word}" if current else word
        wrapped.append(current)
    return "\n".join(wrapped)


def rules_for_learner() -> list[str]:
    """The rules of every lesson, as a learner reads them."""
    return [axiom.rule for axiom in AXIOMS]


def offered() -> Sequence[Subject]:
    """Every subject, as a learner is offered them: the general one last."""
    return [SUBJECTS[key] for key in SUBJECT_KEYS]
