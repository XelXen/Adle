"""The example part a lesson's writer is shown: one for each way a subject is taught.

ADR-061. A model follows an example more closely than a rule, so a lesson of chemistry is
shown an experiment, a lesson of grammar a sentence at work, a lesson of history a
timeline: each obeys the axioms (``lessons/axioms.py``: the case first and alone, the rule
last and made from it) in its own subject's way. ``Subject.example`` names the one a
subject is shown.

Each is a part as a model would write it, and is drawn like any slide: the player steps
through every one of them (``tools/export_slides.py``, ``npm run slides``). The facts in
them are real ones, and a made-up case says that it is made up.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Example:
    #: What the part teaches, to finish "An example, for a part on ...".
    about: str
    #: How it obeys the rules, said to the writer in one sentence.
    order: str
    #: The part, as a model would write it.
    part: dict[str, Any]


EXAMPLES: dict[str, Example] = {
    "area": Example(
        about="why the area of a rectangle is height times width",
        order="The case comes first and alone, then the count in its own numbers, out of the "
        "picture, then the rule",
        part={
            "type": "explanation",
            "title": "Area counts squares",
            "beats": [
                {"say": "Here is a rectangle made of small squares. [Count one row]: four squares."},
                {"say": "There are [three rows] like it, so there are [three times four], twelve squares."},
                {"say": "[Every rectangle] works the same way: its area is its height times its width."},
            ],
            "visual": {
                "elements": [
                    {"id": "g", "kind": "grid", "place": "left",
                     "rows": [["", "", "", ""], ["", "", "", ""], ["", "", "", ""]]},
                    {"id": "w", "kind": "brace", "over": "g.row 1", "side": "above", "label": "4",
                     "color": "blue"},
                    {"id": "h", "kind": "brace", "over": "g.col 1", "side": "left", "label": "3",
                     "color": "green"},
                    {"id": "area", "kind": "math", "place": "right",
                     "tex": "{{\\color{green}{3}}} \\times {{\\color{blue}{4}}} = 12"},
                    {"id": "rule", "kind": "math", "place": "right",
                     "tex": "{{\\color{green}{h}}} \\times {{\\color{blue}{w}}} = A"},
                ],
                "steps": [
                    [{"show": "g"}],
                    [{"color": "g.row 1", "to": "blue"}, {"show": "w"}],
                    [{"color": "g.col 1", "to": "green"}, {"show": "h"}],
                    [{"show": "area", "from": ["h", "w"]}],
                    [{"transform": "area", "into": "rule"}],
                ],
                "description": "3 rows of 4 squares, then $3 \\times 4 = 12$, then $h \\times w = A$.",
            },
        },
    ),
    "falling": Example(
        about="how far a dropped ball falls",
        order="The thing happens first, then it is measured, then the law comes out of the "
        "readings, with its units",
        part={
            "type": "explanation",
            "title": "How far a dropped ball falls",
            "beats": [
                {"say": "Let go of a ball from a high window, and watch where it is as the seconds pass."},
                {"say": "[After one second] it has fallen about five meters. [After two seconds], about twenty: four times as far, not twice."},
                {"say": "Twenty is [five times two squared]. The distance grows with the square of the time: [d is about five t squared], with d in meters and t in seconds."},
            ],
            "visual": {
                "elements": [
                    {"id": "drop", "kind": "number_line", "x": [0, 20], "place": "top",
                     "label": "meters fallen"},
                    {"id": "ball", "kind": "point", "on": "drop", "x": 0, "color": "orange"},
                    {"id": "t", "kind": "number", "value": 0, "decimals": 0, "label": "seconds",
                     "place": "left", "color": "blue"},
                    {"id": "d", "kind": "number", "value": 0, "decimals": 0, "label": "meters",
                     "place": "left", "color": "orange"},
                    {"id": "case", "kind": "math", "place": "right",
                     "tex": "{{\\color{orange}{20}}} = 5 \\times {{\\color{blue}{2}}} ^2"},
                    {"id": "law", "kind": "math", "place": "right",
                     "tex": "{{\\color{orange}{d}}} = 5 \\times {{\\color{blue}{t}}} ^2"},
                ],
                "steps": [
                    [{"show": ["drop", "ball", "t", "d"]}],
                    [{"set": "ball", "to": 5}, {"set": "t", "to": 1}, {"set": "d", "to": 5}],
                    [{"set": "ball", "to": 20}, {"set": "t", "to": 2}, {"set": "d", "to": 20}],
                    [{"show": "case", "from": ["d", "t"]}],
                    [{"transform": "case", "into": "law"}],
                ],
                "description": "A ball on a line of meters fallen: at 0, at 5 after one second, at 20 after two. Then $20 = 5 \\times 2^2$, then $d = 5 \\times t^2$.",
            },
        },
    ),
    "experiment": Example(
        about="what happens when baking soda meets vinegar",
        order="The experiment comes first: what is put together and what is seen. Then the "
        "particle that was seen, then the equation, the gas in the color it had",
        part={
            "type": "explanation",
            "title": "Baking soda meets vinegar",
            "beats": [
                {"say": "Here is a glass of vinegar, with a spoonful of baking soda, a white powder, just dropped into it."},
                {"say": "[It fizzes at once]: bubbles of a gas rise through the vinegar, and the powder is gone."},
                {"say": "[The gas is carbon dioxide]: one carbon atom joined to two oxygen atoms. The powder and the acid in the vinegar have become new substances, and [the equation] names them: sodium acetate, water, and the gas you saw."},
            ],
            "visual": {
                "elements": [
                    {"id": "glass", "kind": "vessel", "shape": "beaker", "liquid": "yellow",
                     "level": 0.6, "solid": "white", "label": "vinegar and baking soda",
                     "place": "left"},
                    {"id": "gas", "kind": "molecule", "atoms": ["O", "C", "O"],
                     "bonds": [[1, 2, 2], [2, 3, 2]], "label": "carbon dioxide",
                     "color": "teal", "place": "right"},
                    {"id": "eq", "kind": "math", "place": "bottom", "size": "small",
                     "tex": "\\mathrm{NaHCO_3} + \\mathrm{CH_3COOH} \\rightarrow \\mathrm{CH_3COONa} + \\mathrm{H_2O} + {} {{\\color{teal}{\\mathrm{CO_2}}}}"},
                ],
                "steps": [
                    [{"show": "glass"}],
                    [{"set": "glass", "to": {"bubbles": True, "solid": False}}],
                    [{"show": "gas"}],
                    [{"show": "eq", "from": ["gas"]}],
                ],
                "description": "A glass of vinegar with white powder at the bottom; it bubbles and the powder goes. A molecule of carbon dioxide, O, C, O. Then the equation, ending in $\\mathrm{CO_2}$.",
            },
        },
    ),
    "leaf": Example(
        about="what a leaf does with light",
        order="One leaf first, then what goes into it and what comes out, one at a time; the "
        "name of the process comes last",
        part={
            "type": "explanation",
            "title": "What a leaf does with light",
            "beats": [
                {"say": "Take one green leaf on a sunny day. Three things reach it: [light from the sun], [water from the roots], and [carbon dioxide from the air]."},
                {"say": "Inside the leaf they are put together. [Out comes sugar], which feeds the plant, and [oxygen], which goes back into the air."},
                {"say": "[That is photosynthesis]: a leaf uses light to turn carbon dioxide and water into sugar and oxygen."},
            ],
            "visual": {
                "elements": [
                    {"id": "leaf", "kind": "shape", "shape": "rectangle", "color": "green",
                     "label": "leaf", "place": "center"},
                    {"id": "light", "kind": "text", "text": "light", "color": "yellow",
                     "place": "top left"},
                    {"id": "water", "kind": "text", "text": "water", "color": "blue",
                     "place": "left"},
                    {"id": "air", "kind": "text", "text": "carbon dioxide", "color": "gray",
                     "place": "bottom left"},
                    {"id": "sugar", "kind": "text", "text": "sugar", "color": "orange",
                     "place": "right"},
                    {"id": "oxygen", "kind": "text", "text": "oxygen", "color": "teal",
                     "place": "top right"},
                    {"id": "in1", "kind": "arrow", "from": "light", "to": "leaf", "color": "yellow"},
                    {"id": "in2", "kind": "arrow", "from": "water", "to": "leaf", "color": "blue"},
                    {"id": "in3", "kind": "arrow", "from": "air", "to": "leaf", "color": "gray"},
                    {"id": "out1", "kind": "arrow", "from": "leaf", "to": "sugar", "color": "orange"},
                    {"id": "out2", "kind": "arrow", "from": "leaf", "to": "oxygen", "color": "teal"},
                    {"id": "name", "kind": "box", "place": "bottom", "color": "green",
                     "text": "Photosynthesis: light turns carbon dioxide and water into sugar and oxygen."},
                ],
                "steps": [
                    [{"show": "leaf"}],
                    [{"show": ["light", "in1"]}],
                    [{"show": ["water", "in2"]}],
                    [{"show": ["air", "in3"]}],
                    [{"show": ["sugar", "out1"]}],
                    [{"show": ["oxygen", "out2"]}],
                    [{"show": "name"}],
                ],
                "description": "A leaf. Light, water and carbon dioxide go into it, one at a time; sugar and oxygen come out. Then the name: photosynthesis.",
            },
        },
    ),
    "water_cycle": Example(
        about="where rain comes from",
        order="One drop of water is followed around, a step at a time; the name of the "
        "whole comes last",
        part={
            "type": "explanation",
            "title": "Where the rain comes from",
            "beats": [
                {"say": "Follow one drop of water in the sea on a warm day."},
                {"say": "[The sun warms it], and it rises into the air as vapor you cannot see. [High up it cools] into the tiny drops of a cloud."},
                {"say": "[The drops grow and fall] as rain, and [rivers carry the water] back to the sea. The same water goes around again and again: [the water cycle]."},
            ],
            "visual": {
                "elements": [
                    {"id": "cycle", "kind": "nodes", "layout": "circle", "place": "left",
                     "color": "blue", "nodes": ["sea", "vapor", "cloud", "rain", "river"],
                     "edges": [["sea", "vapor"], ["vapor", "cloud"], ["cloud", "rain"],
                               ["rain", "river"], ["river", "sea"]]},
                    {"id": "name", "kind": "box", "place": "right", "color": "teal",
                     "text": "The water cycle: the sun lifts water up, and gravity brings it back down."},
                ],
                "steps": [
                    [{"show": "cycle.sea"}],
                    [{"show": ["cycle.vapor", "cycle.sea->vapor"]}],
                    [{"show": ["cycle.cloud", "cycle.vapor->cloud"]}],
                    [{"show": ["cycle.rain", "cycle.cloud->rain"]}],
                    [{"show": ["cycle.river", "cycle.rain->river", "cycle.river->sea"]}],
                    [{"show": "name"}],
                ],
                "description": "Sea, vapor, cloud, rain and river in a circle, an arrow from each to the next and from the river back to the sea. Then the name: the water cycle.",
            },
        },
    ),
    "trace": Example(
        about="finding the largest number in a list",
        order="One small input is run by hand first; the code comes after, the line being run "
        "pointed at; the idea is said last",
        part={
            "type": "explanation",
            "title": "Finding the largest number",
            "beats": [
                {"say": "Here are three numbers in a list. Find the largest by hand, looking at one at a time."},
                {"say": "Call the first one the best so far: [seven]. [The next is twelve], which is larger, so the best becomes twelve. [The last is nine]: smaller, so nothing changes."},
                {"say": "[The code does exactly that]. It starts with the first, and [replaces the best whenever a larger one comes]. [One pass through the list is enough]."},
            ],
            "visual": {
                "elements": [
                    {"id": "nums", "kind": "grid", "rows": [["7", "12", "9"]], "label": "nums",
                     "place": "top left"},
                    {"id": "best", "kind": "number", "value": 7, "decimals": 0, "label": "best",
                     "place": "bottom left", "color": "orange"},
                    {"id": "code", "kind": "code", "label": "Python", "place": "top right",
                     "lines": ["best = nums[0]", "for n in nums:", "    if n > best:",
                               "        best = n"]},
                    {"id": "idea", "kind": "box", "place": "bottom right", "color": "violet",
                     "text": "Keep the best so far. One pass is enough."},
                ],
                "steps": [
                    [{"show": "nums"}],
                    [{"highlight": "nums.1.1"}, {"show": "best"}],
                    [{"highlight": "nums.1.2"}, {"set": "best", "to": 12}],
                    [{"highlight": "nums.1.3"}],
                    [{"show": "code"}, {"highlight": "code.1"}],
                    [{"highlight": ["code.3", "code.4"]}],
                    [{"show": "idea"}],
                ],
                "description": "A list of 7, 12 and 9, and the best so far: 7, then 12. Then four lines of Python that do the same, and the idea: keep the best so far.",
            },
        },
    ),
    "sentence": Example(
        about="how a sentence is made passive",
        order="A real sentence comes first and is worked on; the second sentence is made out "
        "of it; the rule is said last, in one line",
        part={
            "type": "explanation",
            "title": "Who did it, and what it was done to",
            "beats": [
                {"say": "Read this sentence: the dog chased the ball. [The dog] does the chasing, and the sentence begins with it."},
                {"say": "Now begin with the ball instead: [the ball was chased by the dog]. The chasing is the same; what the sentence is about has changed."},
                {"say": "[Two small words came in]: was, and by. That is the passive: [what is acted on comes first], and the one who acts moves to the end."},
            ],
            "visual": {
                "elements": [
                    {"id": "active", "kind": "words", "text": "The dog chased the ball.",
                     "place": "top"},
                    {"id": "doer", "kind": "label", "on": "active.1-2", "text": "does it",
                     "side": "above", "color": "orange"},
                    {"id": "passive", "kind": "words", "text": "The ball was chased by the dog.",
                     "place": "top"},
                    {"id": "rule", "kind": "box", "place": "bottom", "color": "violet",
                     "text": "Passive: what is acted on, then was, then what was done."},
                ],
                "steps": [
                    [{"show": "active"}],
                    [{"color": "active.1-2", "to": "orange"}, {"show": "doer"}],
                    [{"show": "passive"}],
                    [{"color": ["passive.was", "passive.by"], "to": "yellow"}],
                    [{"show": "rule"}],
                ],
                "description": "“The dog chased the ball.” with “The dog” marked as the doer; then “The ball was chased by the dog.”, with “was” and “by” marked; then the rule.",
            },
        },
    ),
    "passage": Example(
        about="the opening of a sonnet",
        order="The lines are quoted first, exactly; the words that do the work are pointed at; "
        "the reading comes last, and rests on those words",
        part={
            "type": "explanation",
            "title": "A comparison that falls short on purpose",
            "beats": [
                {"say": "Read the first line of Shakespeare's eighteenth sonnet: shall I compare thee to a summer's day?"},
                {"say": "[A summer's day] is about the best thing the speaker can think of. [The second line] answers the question: thou art more lovely and more temperate."},
                {"say": "[The word more, twice]: the person is better than the comparison. [Praise by a comparison that is not good enough] runs through the whole poem."},
            ],
            "visual": {
                "elements": [
                    {"id": "one", "kind": "words", "place": "top",
                     "text": "Shall I compare thee to a summer's day?"},
                    {"id": "two", "kind": "words", "place": "top",
                     "text": "Thou art more lovely and more temperate."},
                    {"id": "reading", "kind": "box", "place": "bottom", "color": "violet",
                     "text": "The comparison is raised only to be beaten."},
                ],
                "steps": [
                    [{"show": "one"}],
                    [{"color": "one.summer's day", "to": "yellow"}],
                    [{"show": "two"}],
                    [{"color": ["two.3", "two.6"], "to": "orange"}],
                    [{"show": "reading"}],
                ],
                "description": "“Shall I compare thee to a summer's day?”, with “summer's day” marked; then “Thou art more lovely and more temperate.”, with both “more” marked; then the reading.",
            },
        },
    ),
    "timeline": Example(
        about="how the race to the Moon began",
        order="One moment comes first, then the events around it in order, then what led to "
        "what; the historian's claim comes last",
        part={
            "type": "explanation",
            "title": "A race with a deadline",
            "beats": [
                {"say": "In October 1957 a metal ball the size of a beach ball circled the Earth, beeping. The Soviet Union had launched Sputnik, the first satellite."},
                {"say": "The United States had been beaten into space. [In 1961] its president set a goal in public: a person on the Moon before the decade was out. [In July 1969], Apollo 11 landed there."},
                {"say": "[One led to the next]: a rival's success, a promise made in public, and the work to keep it. [A historian would say] that the landing came out of that rivalry as much as out of science."},
            ],
            "visual": {
                "elements": [
                    {"id": "years", "kind": "timeline", "place": "top", "color": "blue",
                     "events": [
                         {"at": "1957", "text": "Sputnik, the first satellite"},
                         {"at": "1961", "text": "Kennedy sets the goal"},
                         {"at": "1969", "text": "Apollo 11 lands on the Moon"}]},
                    {"id": "why", "kind": "nodes", "layout": "row", "place": "bottom left",
                     "color": "orange",
                     "nodes": ["a rival ahead", "a promise", "the landing"],
                     "edges": [[1, 2], [2, 3]]},
                    {"id": "claim", "kind": "box", "place": "bottom right", "color": "violet",
                     "text": "The landing came out of a rivalry."},
                ],
                "steps": [
                    [{"show": "years.1"}],
                    [{"show": "years.2"}],
                    [{"show": "years.3"}],
                    [{"show": "why"}],
                    [{"show": "claim"}],
                ],
                "description": "A timeline: 1957, Sputnik; 1961, Kennedy sets the goal; 1969, Apollo 11 lands on the Moon. Then a rival ahead leading to a promise leading to the landing, and the claim.",
            },
        },
    ),
    "demand": Example(
        about="what a higher price does to how much is bought",
        order="One small situation with numbers comes first; one thing is changed and the rest "
        "is watched; the principle comes last, with what it assumes",
        part={
            "type": "explanation",
            "title": "A higher price, fewer buyers",
            "beats": [
                {"say": "Picture a stand that sells lemonade at one dollar a cup. Forty people buy a cup."},
                {"say": "[Raise the price to two dollars]. Now only twenty people think it is worth it. [At three dollars], ten."},
                {"say": "[Each time the price went up, fewer cups were sold]. That is the law of demand, and it holds when nothing else changes: the same day, the same weather, the same lemonade."},
            ],
            "visual": {
                "elements": [
                    {"id": "sold", "kind": "bars", "place": "center", "color": "blue",
                     "label": "cups sold", "labels": ["1 dollar", "2 dollars", "3 dollars"],
                     "values": [40, 20, 10]},
                    {"id": "law", "kind": "box", "place": "bottom", "color": "violet",
                     "text": "When the price rises and nothing else changes, people buy less."},
                ],
                "steps": [
                    [{"show": "sold.1"}],
                    [{"show": "sold.2"}],
                    [{"show": "sold.3"}],
                    [{"show": "law"}],
                ],
                "description": "Bars of cups sold: 40 at 1 dollar, 20 at 2 dollars, 10 at 3 dollars. Then the law of demand.",
            },
        },
    ),
    "common_cause": Example(
        about="why two things that rise together need not cause each other",
        order="One made-up case comes first, and says it is made up; then what explains it; "
        "the general idea comes last",
        part={
            "type": "explanation",
            "title": "Rising together is not causing",
            "beats": [
                {"say": "Picture a seaside town. The months when most ice cream is sold are also the months when most swimmers need rescuing."},
                {"say": "[Both are high in July]. Does ice cream make swimming dangerous? Look for something behind both: [hot weather]. Heat sells ice cream, and heat sends people into the sea."},
                {"say": "[Two things can rise together because a third drives them both]. Before saying that one causes the other, ask what else changed."},
            ],
            "visual": {
                "elements": [
                    {"id": "months", "kind": "table", "place": "left",
                     "header": ["month", "ice creams", "rescues"],
                     "rows": [["March", "200", "1"], ["July", "900", "8"]]},
                    {"id": "why", "kind": "nodes", "layout": "tree", "place": "right",
                     "color": "orange", "nodes": ["hot weather", "ice cream", "swimming"],
                     "edges": [[1, 2], [1, 3]]},
                    {"id": "rule", "kind": "box", "place": "bottom", "color": "violet",
                     "text": "Rising together does not show that one causes the other."},
                ],
                "steps": [
                    [{"show": "months"}],
                    [{"color": "months.row 2", "to": "yellow"}],
                    [{"show": "why"}],
                    [{"show": "rule"}],
                ],
                "description": "A table of ice creams sold and rescues in March and in July, both higher in July. Then hot weather leading to both, and the idea.",
            },
        },
    ),
    "meter": Example(
        about="beats that come in threes",
        order="One pattern comes first, counted out; what repeats in it is marked; its name "
        "comes last",
        part={
            "type": "explanation",
            "title": "Counting in threes",
            "beats": [
                {"say": "Clap this steadily and count along: one, two, three, one, two, three."},
                {"say": "Now [clap the ones harder]. The beats fall into groups of three, each beginning with a strong one: strong, weak, weak."},
                {"say": "[That grouping is the meter]. Three beats to a group is triple meter, the sway of a waltz."},
            ],
            "visual": {
                "elements": [
                    {"id": "beats", "kind": "grid", "rows": [["1", "2", "3", "1", "2", "3"]],
                     "place": "center", "label": "claps"},
                    {"id": "group", "kind": "brace", "side": "below", "label": "one group",
                     "color": "orange", "over": ["beats.1.1", "beats.1.2", "beats.1.3"]},
                    {"id": "name", "kind": "box", "place": "bottom", "color": "violet",
                     "text": "Triple meter: beats in threes, the first one strong."},
                ],
                "steps": [
                    [{"show": "beats"}],
                    [{"color": ["beats.1.1", "beats.1.4"], "to": "orange"}, {"show": "group"}],
                    [{"show": "name"}],
                ],
                "description": "Six claps in a row, counted 1, 2, 3, 1, 2, 3, the ones marked; a brace under the first three; then the name: triple meter.",
            },
        },
    ),
}  # fmt: skip


def written(key: str) -> str:
    """An example as the writer of a lesson is shown it: what it is for, how it obeys the
    rules, and the part itself as JSON, a line to each beat, element and step."""
    example = EXAMPLES[key]
    part = example.part
    visual = part["visual"]

    def one(value: object) -> str:
        return json.dumps(value, ensure_ascii=False)

    lines = [
        f"An example, for a part on {example.about}. {example.order}:",
        f'{{"type": {one(part["type"])}, "title": {one(part["title"])},',
        ' "beats": [' + ",\n  ".join(one(beat) for beat in part["beats"]) + "],",
        ' "visual": {"elements": [',
        ",\n".join("   " + one(element) for element in visual["elements"]) + "],",
        '  "steps": [' + ",\n   ".join(one(step) for step in visual["steps"]) + "],",
        f'  "description": {one(visual["description"])}}}}}',
    ]
    return "\n".join(lines)
