"""Rules for a course's concept graph.

Pure functions over plain values: no database, no framework. The application
layer loads concepts, asks these functions what is true, and stores the result.

A course is a directed graph. "B needs A" means A is a prerequisite of B. The
graph must stay free of loops and every prerequisite must exist; otherwise
there is no order in which the course could be learned (PLAN.md 7.2).
"""

from __future__ import annotations

import heapq
from collections import deque
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from enum import StrEnum


class GraphError(ValueError):
    """The graph has no valid learning order (it contains a loop)."""


class Severity(StrEnum):
    #: The course cannot be started until this is fixed.
    ERROR = "error"
    #: Worth a look; does not block learning.
    WARNING = "warning"


class IssueCode(StrEnum):
    CYCLE = "cycle"
    UNKNOWN_PREREQUISITE = "unknown_prerequisite"
    SELF_PREREQUISITE = "self_prerequisite"
    DUPLICATE_PREREQUISITE = "duplicate_prerequisite"
    DUPLICATE_TITLE = "duplicate_title"
    NO_OBJECTIVE = "no_objective"


@dataclass(frozen=True, slots=True)
class ConceptNode:
    id: str
    title: str
    #: Ids of the concepts this one needs first.
    prerequisites: tuple[str, ...] = ()
    objective_count: int = 1


@dataclass(frozen=True, slots=True)
class GraphIssue:
    code: IssueCode
    severity: Severity
    #: The concepts involved. For a loop: the loop itself, in "needs" order.
    concept_ids: tuple[str, ...]
    #: A sentence a learner can act on.
    message: str


def _usable_edges(nodes: Sequence[ConceptNode]) -> dict[str, tuple[str, ...]]:
    """Prerequisites per concept, keeping only links between existing, different concepts."""
    known = {node.id for node in nodes}
    edges: dict[str, tuple[str, ...]] = {}
    for node in nodes:
        kept = dict.fromkeys(
            prerequisite
            for prerequisite in node.prerequisites
            if prerequisite in known and prerequisite != node.id
        )
        edges[node.id] = tuple(kept)
    return edges


def _shortest_path(
    edges: dict[str, tuple[str, ...]], start: str, goal: str, within: Collection[str] | None = None
) -> tuple[str, ...] | None:
    """Shortest chain ``start needs … needs goal``, or ``None``. ``start != goal``."""
    previous: dict[str, str] = {}
    queue = deque([start])
    seen = {start}
    while queue:
        current = queue.popleft()
        for following in edges.get(current, ()):
            if following in seen or (within is not None and following not in within):
                continue
            previous[following] = current
            if following == goal:
                path = [goal]
                while path[-1] != start:
                    path.append(previous[path[-1]])
                return tuple(reversed(path))
            seen.add(following)
            queue.append(following)
    return None


def _strongly_connected(order: Sequence[str], edges: dict[str, tuple[str, ...]]) -> list[list[str]]:
    """Tarjan's algorithm, written without recursion so a long chain cannot overflow the stack."""
    index_of: dict[str, int] = {}
    lowest: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    components: list[list[str]] = []
    counter = 0

    for root in order:
        if root in index_of:
            continue
        work: list[tuple[str, int]] = [(root, 0)]
        while work:
            node, position = work.pop()
            if position == 0:
                index_of[node] = lowest[node] = counter
                counter += 1
                stack.append(node)
                on_stack.add(node)
            followers = edges.get(node, ())
            descended = False
            for offset in range(position, len(followers)):
                following = followers[offset]
                if following not in index_of:
                    work.append((node, offset + 1))
                    work.append((following, 0))
                    descended = True
                    break
                if following in on_stack:
                    lowest[node] = min(lowest[node], index_of[following])
            if descended:
                continue
            if lowest[node] == index_of[node]:
                component: list[str] = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)
                    if member == node:
                        break
                components.append(component)
            if work:
                parent = work[-1][0]
                lowest[parent] = min(lowest[parent], lowest[node])
    return components


def find_cycles(nodes: Sequence[ConceptNode]) -> list[tuple[str, ...]]:
    """One loop for every group of concepts that depend on each other.

    A loop is returned as a path in "needs" order: ``(a, b, c)`` means a needs
    b, b needs c, and c needs a. The result is deterministic and follows the
    order of ``nodes``. A concept that lists itself is reported by
    :func:`validate` as its own kind of problem, not here.
    """
    order = [node.id for node in nodes]
    position = {concept_id: index for index, concept_id in enumerate(order)}
    edges = _usable_edges(nodes)
    cycles: list[tuple[str, ...]] = []
    for component in _strongly_connected(order, edges):
        if len(component) < 2:
            continue
        members = set(component)
        start = min(component, key=position.__getitem__)
        # The shortest loop through the earliest member is the easiest to explain.
        best: tuple[str, ...] | None = None
        for following in edges[start]:
            if following not in members:
                continue
            back = _shortest_path(edges, following, start, members)
            if back is not None and (best is None or len(back) < len(best)):
                best = back
        if best is not None:
            cycles.append((start, *best[:-1]))
    cycles.sort(key=lambda cycle: position[cycle[0]])
    return cycles


def loop_if_added(
    nodes: Sequence[ConceptNode], concept_id: str, prerequisite_id: str
) -> tuple[str, ...] | None:
    """The loop that "``concept_id`` needs ``prerequisite_id``" would close, if any.

    Returned in "needs" order starting at ``concept_id``.
    """
    if concept_id == prerequisite_id:
        return (concept_id,)
    path = _shortest_path(_usable_edges(nodes), prerequisite_id, concept_id)
    return None if path is None else (concept_id, *path[:-1])


def learning_order(nodes: Sequence[ConceptNode]) -> list[str]:
    """Concept ids in an order where each comes after everything it needs.

    Among the concepts that are ready at any point, the one that appears first
    in ``nodes`` (the learner's own order) goes first. Reordering the list
    therefore changes the path wherever the prerequisites leave a choice.

    Raises :class:`GraphError` if the graph contains a loop. Links to concepts
    that do not exist are ignored here; :func:`validate` reports them.
    """
    edges = _usable_edges(nodes)
    position = {node.id: index for index, node in enumerate(nodes)}
    waiting_on = {concept_id: len(needed) for concept_id, needed in edges.items()}
    unlocks: dict[str, list[str]] = {concept_id: [] for concept_id in edges}
    for concept_id, needed in edges.items():
        for prerequisite in needed:
            unlocks[prerequisite].append(concept_id)

    ready = [position[concept_id] for concept_id, count in waiting_on.items() if count == 0]
    heapq.heapify(ready)
    ids = [node.id for node in nodes]
    ordered: list[str] = []
    while ready:
        concept_id = ids[heapq.heappop(ready)]
        ordered.append(concept_id)
        for dependent in unlocks[concept_id]:
            waiting_on[dependent] -= 1
            if waiting_on[dependent] == 0:
                heapq.heappush(ready, position[dependent])
    if len(ordered) != len(edges):
        raise GraphError("The concepts depend on each other in a loop.")
    return ordered


def layers(nodes: Sequence[ConceptNode]) -> dict[str, int]:
    """How deep each concept sits: 0 if it needs nothing, else one below its deepest prerequisite.

    Used to draw the map. Raises :class:`GraphError` if the graph contains a loop.
    """
    edges = _usable_edges(nodes)
    depth: dict[str, int] = {}
    for concept_id in learning_order(nodes):
        depth[concept_id] = 1 + max((depth[needed] for needed in edges[concept_id]), default=-1)
    return depth


def everything_needed_by(nodes: Sequence[ConceptNode], concept_id: str) -> frozenset[str]:
    """Every concept that must come before ``concept_id``, directly or through others."""
    return _reachable(_usable_edges(nodes), concept_id)


def everything_that_needs(nodes: Sequence[ConceptNode], concept_id: str) -> frozenset[str]:
    """Every concept that depends on ``concept_id``, directly or through others."""
    reverse: dict[str, list[str]] = {node.id: [] for node in nodes}
    for dependent, needed in _usable_edges(nodes).items():
        for prerequisite in needed:
            reverse[prerequisite].append(dependent)
    return _reachable({key: tuple(value) for key, value in reverse.items()}, concept_id)


def _reachable(edges: dict[str, tuple[str, ...]], start: str) -> frozenset[str]:
    seen: set[str] = set()
    queue = deque(edges.get(start, ()))
    while queue:
        current = queue.popleft()
        if current in seen or current == start:
            continue
        seen.add(current)
        queue.extend(edges.get(current, ()))
    return frozenset(seen)


def ready_to_learn(nodes: Sequence[ConceptNode], supported: Collection[str]) -> list[str]:
    """Concepts not yet supported whose prerequisites all are, in the learner's order.

    ``supported`` holds the concepts the learner has shown enough understanding
    of to build on. Works on any graph: a concept inside a loop is simply never
    ready.
    """
    edges = _usable_edges(nodes)
    return [
        node.id
        for node in nodes
        if node.id not in supported and all(needed in supported for needed in edges[node.id])
    ]


def _quoted(title: str) -> str:
    return f"“{title}”"


def _normalised_title(title: str) -> str:
    return " ".join(title.split()).casefold()


def validate(nodes: Sequence[ConceptNode]) -> list[GraphIssue]:
    """Everything wrong with the graph: errors first, then warnings, in a stable order."""
    titles = {node.id: node.title for node in nodes}
    known = set(titles)
    errors: list[GraphIssue] = []
    warnings: list[GraphIssue] = []

    for node in nodes:
        seen: set[str] = set()
        for prerequisite in node.prerequisites:
            if prerequisite == node.id:
                errors.append(
                    GraphIssue(
                        IssueCode.SELF_PREREQUISITE,
                        Severity.ERROR,
                        (node.id,),
                        f"{_quoted(node.title)} lists itself as something to learn first.",
                    )
                )
            elif prerequisite not in known:
                errors.append(
                    GraphIssue(
                        IssueCode.UNKNOWN_PREREQUISITE,
                        Severity.ERROR,
                        (node.id,),
                        f"{_quoted(node.title)} needs a concept that no longer exists.",
                    )
                )
            elif prerequisite in seen:
                warnings.append(
                    GraphIssue(
                        IssueCode.DUPLICATE_PREREQUISITE,
                        Severity.WARNING,
                        (node.id, prerequisite),
                        f"{_quoted(node.title)} lists {_quoted(titles[prerequisite])} twice.",
                    )
                )
            seen.add(prerequisite)

    for cycle in find_cycles(nodes):
        chain = " needs ".join(_quoted(titles[concept_id]) for concept_id in (*cycle, cycle[0]))
        errors.append(
            GraphIssue(
                IssueCode.CYCLE,
                Severity.ERROR,
                cycle,
                f"These concepts need each other in a loop: {chain}. "
                "Remove one of the links so there is somewhere to start.",
            )
        )

    by_title: dict[str, list[ConceptNode]] = {}
    for node in nodes:
        by_title.setdefault(_normalised_title(node.title), []).append(node)
    for same in by_title.values():
        if len(same) > 1:
            warnings.append(
                GraphIssue(
                    IssueCode.DUPLICATE_TITLE,
                    Severity.WARNING,
                    tuple(node.id for node in same),
                    f"{len(same)} concepts are called {_quoted(same[0].title)}. "
                    "Rename them so they are easy to tell apart.",
                )
            )

    for node in nodes:
        if node.objective_count < 1:
            warnings.append(
                GraphIssue(
                    IssueCode.NO_OBJECTIVE,
                    Severity.WARNING,
                    (node.id,),
                    f"{_quoted(node.title)} has no learning objective yet, "
                    "so there is nothing to check understanding against.",
                )
            )

    return [*errors, *warnings]


def has_errors(issues: Sequence[GraphIssue]) -> bool:
    return any(issue.severity is Severity.ERROR for issue in issues)
