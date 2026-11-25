"""Which provider a request goes to, when the learner has more than one.

Pure rules: no clock, no database, no network. The caller says what the request is for,
what the learner chose, and how each provider stands; the answer is the providers to ask,
in order, and the reason for the order in words a learner can read.

Used together, each provider does what it was measured to do well (ADR-023, ADR-039):
each says what it is asked first for (``Standing.first_for``). AIHubMix's model is made
for code, so it draws the pictures, and its small daily allowance goes on them alone;
NVIDIA writes everything else, with the model that does each soonest. If the provider
asked cannot answer, the other is asked, and that is said.

None of this happens unless the learner chose it: with one provider selected, that
provider is the whole plan, whatever happens to it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

#: The learner's choice that lets Adle use every provider it has a key for.
AUTOMATIC = "auto"

#: What a request is for, as far as choosing a provider goes. ``ask`` is a question the
#: learner puts to Adle in the middle of a lesson; ``check`` finds out whether a key works;
#: ``read`` reads a picture of a page of the learner's own (ADR-060); ``film`` writes a
#: chapter of a film of a whole course (ADR-065); ``storyboard`` looks over the pictures of
#: one chapter of a film (ADR-066).
Purpose = Literal["ask", "curriculum", "lesson", "scene", "check", "read", "film", "storyboard"]
PURPOSES: tuple[Purpose, ...] = (
    "ask",
    "curriculum",
    "lesson",
    "scene",
    "check",
    "read",
    "film",
    "storyboard",
)
#: What is sent with pictures: only a model that sees them can be asked it (ADR-060).
PICTURE_PURPOSES: frozenset[str] = frozenset({"read", "storyboard"})


@dataclass(frozen=True, slots=True)
class Standing:
    """One provider, as it stands at this moment."""

    provider_id: str
    name: str
    has_key: bool
    #: What it is asked first for, when the learner lets Adle choose.
    first_for: frozenset[str] = frozenset(PURPOSES)
    #: The larger of the shares of today's requests and of today's tokens already used.
    used: float = 0.0
    #: Nothing more can be sent to it today.
    spent: bool = False
    #: It failed a moment ago and is being left alone for a while.
    resting: bool = False
    #: What it can be asked at all: a provider with no model that sees pictures cannot be
    #: asked to read one, by choice or otherwise.
    serves: frozenset[str] = frozenset(PURPOSES)

    @property
    def ready(self) -> bool:
        return not self.spent and not self.resting


@dataclass(frozen=True, slots=True)
class Plan:
    """The providers to ask for one request, in order, and why in that order."""

    provider_ids: tuple[str, ...]
    names: tuple[str, ...]
    #: Whether the learner let Adle choose (and so whether a second provider may be asked).
    automatic: bool
    #: Why the first is first, in a sentence. Empty when there was nothing to decide.
    reason: str = ""

    @property
    def sentence(self) -> str:
        """Where the request will go, to put after "Sends to": never less than the truth."""
        if not self.names:
            return ""
        if len(self.names) == 1:
            return self.names[0]
        first, *others = self.names
        return f"{first}, then {' or '.join(others)} if needed"


def _why_not(standing: Standing) -> str:
    if standing.spent:
        return f"{standing.name} has no allowance left today."
    return f"{standing.name} couldn’t answer earlier, so it’s paused for now."


def _why_first(purpose: str, first: Standing, others: Sequence[Standing]) -> str:
    if purpose == "scene":
        return f"{first.name} draws the pictures: its model is made for code."
    # Kept for the pictures: asked first for them, and not for this.
    kept = next(
        (
            other
            for other in others
            if "scene" in other.first_for and purpose not in other.first_for
        ),
        None,
    )
    if kept is not None:
        return f"{first.name} writes this, and {kept.name} is kept for the pictures."
    return ""


def _order(purpose: str, standings: Sequence[Standing]) -> tuple[list[Standing], str]:
    """Usable providers, best first, for this purpose; and why the first is first."""
    usable = [standing for standing in standings if standing.has_key and purpose in standing.serves]
    if len(usable) < 2:
        return usable, ""

    meant = [standing for standing in usable if purpose in standing.first_for]
    first = [standing for standing in meant if standing.ready]
    if first:
        others = [standing for standing in usable if standing is not first[0]]
        reason = _why_first(purpose, first[0], others)
    else:
        # The one meant for this cannot be asked just now: the next that can be is asked
        # instead. The reason given is about the one that is away, not the one used.
        first = [standing for standing in usable if standing.ready]
        reason = _why_not(meant[0]) if meant else ""

    chosen = first[:1]
    # Then everything else that can still be asked today, with what is resting last: a
    # provider that failed a moment ago is still better than giving up.
    rest = [standing for standing in usable if standing not in chosen and not standing.spent]
    rest.sort(key=lambda standing: standing.resting)
    ordered = [*chosen, *rest]
    if not ordered:
        # Every provider has used up its day. The first one says so.
        ordered = usable[:1]
        reason = ""
    return ordered, reason


def plan(purpose: str, selection: str, standings: Sequence[Standing]) -> Plan:
    """The providers to ask for a request, given what the learner chose.

    ``selection`` is a provider's name, or ``AUTOMATIC``. A selection Adle does not know is
    treated as automatic: the learner's keys still say which providers they agreed to.
    """
    known = {standing.provider_id: standing for standing in standings}
    chosen = known.get(selection)
    if chosen is not None:
        # One provider, by the learner's choice. Nothing moves a request away from it, and
        # a request it cannot be asked at all goes nowhere: the plan is empty.
        if purpose not in chosen.serves:
            return Plan((), (), automatic=False)
        return Plan((chosen.provider_id,), (chosen.name,), automatic=False)
    ordered, reason = _order(purpose, standings)
    if not ordered:
        # No key anywhere it could go. The first provider that could be asked is named so
        # that the refusal can say whose key is missing; nothing is sent. None at all, and
        # the plan is empty.
        ordered = [standing for standing in standings if purpose in standing.serves][:1]
    return Plan(
        tuple(standing.provider_id for standing in ordered),
        tuple(standing.name for standing in ordered),
        automatic=True,
        reason=reason,
    )
