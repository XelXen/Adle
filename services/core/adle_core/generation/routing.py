"""Which provider a request goes to, when the learner has more than one.

Pure rules: no clock, no database, no network. The caller says what the request is for,
what the learner chose, and how each provider stands; the answer is the providers to ask,
in order, and the reason for the order in words a learner can read.

Two providers can differ in exactly the way that matters here. One answers quickly and
allows little in a day; the other is slow and allows a great deal. Used together, each
does what it is good at (ADR-023):

* what the learner is sitting and waiting for (a question asked in the middle of a
  lesson, a list of suggested concepts, a check that a key works) goes to the quick one,
  for as long as it has any allowance left;
* long work (a lesson, a picture) goes to the quick one too while most of its day is
  still unspent, and to the roomy one once it is not, so that the quick one always has
  something left for what is waited for;
* if the provider asked cannot answer, the other is asked, and that is said.

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
#: learner puts to Adle in the middle of a lesson; ``check`` finds out whether a key works.
Purpose = Literal["ask", "curriculum", "lesson", "scene", "check"]

#: Requests the learner sits and waits for. They go to the quick provider first, always.
WAITED_FOR: frozenset[str] = frozenset({"ask", "curriculum", "check"})

#: Long work stops going to a provider with a small daily allowance once this share of
#: either its requests or its tokens is spent, so that what is left is there for the
#: requests the learner waits for.
HEAVY_WORK_SHARE = 0.5


@dataclass(frozen=True, slots=True)
class Standing:
    """One provider, as it stands at this moment."""

    provider_id: str
    name: str
    has_key: bool
    #: It answers in seconds rather than minutes.
    quick: bool
    #: Its daily allowance is small enough to plan around.
    limited: bool
    #: The larger of the shares of today's requests and of today's tokens already used.
    used: float = 0.0
    #: Nothing more can be sent to it today.
    spent: bool = False
    #: It failed a moment ago and is being left alone for a while.
    resting: bool = False

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


def _order(purpose: str, standings: Sequence[Standing]) -> tuple[list[Standing], str]:
    """Usable providers, best first, for this purpose; and why the first is first."""
    usable = [standing for standing in standings if standing.has_key]
    if len(usable) < 2:
        return usable, ""

    quick = [standing for standing in usable if standing.quick]
    roomy = [standing for standing in usable if not standing.limited]
    reason = ""

    if purpose in WAITED_FOR:
        # Quick first, whatever is left of its day.
        first = [standing for standing in quick if standing.ready]
        if first:
            reason = f"{first[0].name} is faster, and you’re waiting on this."
        elif quick:
            reason = _why_not(quick[0])
    else:
        # Quick first only while most of its day is unspent; otherwise it is kept for
        # the requests the learner waits for.
        first = [
            standing
            for standing in quick
            if standing.ready and (not standing.limited or standing.used < HEAVY_WORK_SHARE)
        ]
        if first:
            reason = f"{first[0].name} is faster, and has plenty of allowance left today."
        else:
            first = [standing for standing in roomy if standing.ready]
            kept = next((standing for standing in quick if standing.limited), None)
            if kept is not None and not kept.ready:
                reason = _why_not(kept)
            elif first and kept is not None:
                reason = f"{kept.name}’s remaining allowance is saved for what you wait on."
            elif not first and roomy:
                # The one with room cannot be asked just now, so the quick one is asked
                # after all. The reason given is about the one that is away, not about
                # the one that is being used.
                reason = _why_not(roomy[0])

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
        # One provider, by the learner's choice. Nothing moves a request away from it.
        return Plan((chosen.provider_id,), (chosen.name,), automatic=False)
    ordered, reason = _order(purpose, standings)
    if not ordered:
        # No key anywhere. The first provider is named so that the refusal can say whose
        # key is missing; nothing is sent.
        ordered = list(standings[:1])
    return Plan(
        tuple(standing.provider_id for standing in ordered),
        tuple(standing.name for standing in ordered),
        automatic=True,
        reason=reason,
    )
