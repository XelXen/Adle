"""The concept graph: what counts as valid, and the order it can be learned in."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from adle_core.curriculum.graph import (
    ConceptNode,
    GraphError,
    IssueCode,
    Severity,
    everything_needed_by,
    everything_that_needs,
    find_cycles,
    has_errors,
    layers,
    learning_order,
    loop_if_added,
    ready_to_learn,
    validate,
)


def node(concept_id: str, *prerequisites: str, title: str | None = None) -> ConceptNode:
    return ConceptNode(
        id=concept_id, title=title or concept_id.upper(), prerequisites=prerequisites
    )


NEURAL_NETWORKS = [
    node("weights"),
    node("activation"),
    node("perceptron", "weights", "activation"),
    node("forward", "perceptron"),
    node("loss", "forward"),
    node("chain-rule"),
    node("backprop", "loss", "chain-rule"),
    node("descent", "backprop"),
]


@st.composite
def acyclic_graphs(draw: st.DrawFn) -> list[ConceptNode]:
    """Random graphs without loops, listed in an order unrelated to their dependencies."""
    count = draw(st.integers(min_value=1, max_value=12))
    ids = [f"c{index}" for index in range(count)]
    # A hidden ranking decides which links are allowed, so the listed order is arbitrary.
    rank = draw(st.permutations(ids))
    nodes = []
    for concept_id in ids:
        earlier = rank[: rank.index(concept_id)]
        prerequisites = (
            draw(st.lists(st.sampled_from(earlier), unique=True, max_size=4)) if earlier else []
        )
        nodes.append(node(concept_id, *prerequisites))
    return nodes


# -- a valid course --------------------------------------------------------


def test_a_well_formed_course_has_no_issues_and_a_learning_order() -> None:
    assert validate(NEURAL_NETWORKS) == []
    order = learning_order(NEURAL_NETWORKS)
    assert order == [
        "weights",
        "activation",
        "perceptron",
        "forward",
        "loss",
        "chain-rule",
        "backprop",
        "descent",
    ]


def test_the_learners_own_order_is_followed_wherever_prerequisites_allow() -> None:
    # "chain-rule" needs nothing, so moving it to the front moves it in the path too.
    reordered = [NEURAL_NETWORKS[5], *NEURAL_NETWORKS[:5], *NEURAL_NETWORKS[6:]]
    assert learning_order(reordered)[0] == "chain-rule"
    # A concept listed before its prerequisite still comes after it.
    backwards = list(reversed(NEURAL_NETWORKS))
    order = learning_order(backwards)
    assert order.index("weights") < order.index("perceptron") < order.index("forward")


def test_layers_place_each_concept_below_everything_it_needs() -> None:
    assert layers(NEURAL_NETWORKS) == {
        "weights": 0,
        "activation": 0,
        "chain-rule": 0,
        "perceptron": 1,
        "forward": 2,
        "loss": 3,
        "backprop": 4,
        "descent": 5,
    }


def test_closures_follow_links_in_both_directions() -> None:
    assert everything_needed_by(NEURAL_NETWORKS, "loss") == {
        "forward",
        "perceptron",
        "weights",
        "activation",
    }
    assert everything_that_needs(NEURAL_NETWORKS, "loss") == {"backprop", "descent"}
    assert everything_needed_by(NEURAL_NETWORKS, "weights") == frozenset()
    assert everything_that_needs(NEURAL_NETWORKS, "descent") == frozenset()


def test_ready_concepts_are_those_whose_prerequisites_are_supported() -> None:
    assert ready_to_learn(NEURAL_NETWORKS, set()) == ["weights", "activation", "chain-rule"]
    assert ready_to_learn(NEURAL_NETWORKS, {"weights"}) == ["activation", "chain-rule"]
    assert ready_to_learn(NEURAL_NETWORKS, {"weights", "activation"}) == [
        "perceptron",
        "chain-rule",
    ]
    everything = {concept.id for concept in NEURAL_NETWORKS}
    assert ready_to_learn(NEURAL_NETWORKS, everything) == []


# -- loops -----------------------------------------------------------------


def test_a_loop_is_reported_once_as_the_path_that_closes_it() -> None:
    graph = [node("a", "b"), node("b", "c"), node("c", "a"), node("d", "a")]
    assert find_cycles(graph) == [("a", "b", "c")]

    issues = validate(graph)
    assert [issue.code for issue in issues] == [IssueCode.CYCLE]
    assert issues[0].severity is Severity.ERROR
    assert issues[0].concept_ids == ("a", "b", "c")
    assert "“A” needs “B” needs “C” needs “A”" in issues[0].message
    assert has_errors(issues)
    with pytest.raises(GraphError):
        learning_order(graph)
    with pytest.raises(GraphError):
        layers(graph)


def test_separate_loops_are_reported_separately_and_bystanders_are_left_out() -> None:
    graph = [
        node("a", "b"),
        node("b", "a"),
        node("free"),
        node("x", "y"),
        node("y", "z"),
        node("z", "x"),
        node("after", "a"),
    ]
    assert find_cycles(graph) == [("a", "b"), ("x", "y", "z")]


def test_the_shortest_loop_through_a_tangle_is_the_one_explained() -> None:
    # a -> b -> c -> a is one loop; a -> c -> a is a shorter one inside it.
    graph = [node("a", "b", "c"), node("b", "c"), node("c", "a")]
    assert find_cycles(graph) == [("a", "c")]


def test_a_concept_inside_a_loop_is_never_ready() -> None:
    graph = [node("a", "b"), node("b", "a"), node("free")]
    assert ready_to_learn(graph, set()) == ["free"]
    assert ready_to_learn(graph, {"free"}) == []


def test_a_new_link_is_checked_before_it_is_made() -> None:
    assert loop_if_added(NEURAL_NETWORKS, "weights", "descent") == (
        "weights",
        "descent",
        "backprop",
        "loss",
        "forward",
        "perceptron",
    )
    assert loop_if_added(NEURAL_NETWORKS, "descent", "weights") is None
    assert loop_if_added(NEURAL_NETWORKS, "loss", "loss") == ("loss",)
    assert loop_if_added(NEURAL_NETWORKS, "loss", "not-a-concept") is None


def test_very_long_chains_do_not_exhaust_the_stack() -> None:
    length = 5_000
    chain = [node(f"n{index}", *([f"n{index - 1}"] if index else [])) for index in range(length)]
    assert learning_order(chain)[-1] == f"n{length - 1}"
    assert find_cycles(chain) == []
    assert layers(chain)[f"n{length - 1}"] == length - 1
    looped = [node("n0", f"n{length - 1}"), *chain[1:]]
    assert len(find_cycles(looped)[0]) == length


# -- other problems --------------------------------------------------------


def test_broken_links_are_errors() -> None:
    graph = [node("a", "a"), node("b", "gone"), node("c", "b")]
    issues = validate(graph)
    assert [(issue.code, issue.concept_ids) for issue in issues] == [
        (IssueCode.SELF_PREREQUISITE, ("a",)),
        (IssueCode.UNKNOWN_PREREQUISITE, ("b",)),
    ]
    assert has_errors(issues)
    # A broken link does not stop the rest of the course from being ordered.
    assert learning_order(graph) == ["a", "b", "c"]


def test_advice_is_given_as_warnings_and_listed_after_errors() -> None:
    graph = [
        node("a", title="Loss"),
        node("b", "a", "a", title="  loss "),
        ConceptNode(id="c", title="Gradient", prerequisites=("c",), objective_count=0),
    ]
    issues = validate(graph)
    assert [(issue.code, issue.severity) for issue in issues] == [
        (IssueCode.SELF_PREREQUISITE, Severity.ERROR),
        (IssueCode.DUPLICATE_PREREQUISITE, Severity.WARNING),
        (IssueCode.DUPLICATE_TITLE, Severity.WARNING),
        (IssueCode.NO_OBJECTIVE, Severity.WARNING),
    ]
    duplicate = issues[2]
    assert duplicate.concept_ids == ("a", "b")
    assert "2 concepts" in duplicate.message


def test_warnings_alone_do_not_block_a_course() -> None:
    graph = [ConceptNode(id="a", title="Loss", objective_count=0)]
    issues = validate(graph)
    assert issues
    assert not has_errors(issues)


def test_an_empty_course_is_valid() -> None:
    assert validate([]) == []
    assert learning_order([]) == []
    assert layers([]) == {}
    assert find_cycles([]) == []
    assert ready_to_learn([], set()) == []


# -- properties ------------------------------------------------------------


@given(acyclic_graphs())
def test_any_graph_without_loops_can_be_ordered(graph: list[ConceptNode]) -> None:
    assert not has_errors(validate(graph))
    assert find_cycles(graph) == []
    order = learning_order(graph)
    assert sorted(order) == sorted(concept.id for concept in graph)
    place = {concept_id: index for index, concept_id in enumerate(order)}
    depth = layers(graph)
    for concept in graph:
        for prerequisite in concept.prerequisites:
            assert place[prerequisite] < place[concept.id]
            assert depth[prerequisite] < depth[concept.id]
        assert (depth[concept.id] == 0) == (not concept.prerequisites)


@given(acyclic_graphs())
def test_without_links_the_learners_order_is_the_learning_order(graph: list[ConceptNode]) -> None:
    unlinked = [node(concept.id) for concept in graph]
    assert learning_order(unlinked) == [concept.id for concept in graph]


@given(acyclic_graphs())
def test_always_taking_the_first_ready_concept_walks_the_learning_order(
    graph: list[ConceptNode],
) -> None:
    supported: set[str] = set()
    walked = []
    while ready := ready_to_learn(graph, supported):
        walked.append(ready[0])
        supported.add(ready[0])
    assert walked == learning_order(graph)


@given(acyclic_graphs(), st.data())
def test_a_link_closes_a_loop_exactly_when_the_check_says_so(
    graph: list[ConceptNode], data: st.DataObject
) -> None:
    ids = [concept.id for concept in graph]
    concept_id = data.draw(st.sampled_from(ids))
    prerequisite_id = data.draw(st.sampled_from(ids))
    predicted = loop_if_added(graph, concept_id, prerequisite_id)
    changed = [
        ConceptNode(
            id=concept.id,
            title=concept.title,
            prerequisites=(*concept.prerequisites, prerequisite_id)
            if concept.id == concept_id
            else concept.prerequisites,
        )
        for concept in graph
    ]
    if concept_id == prerequisite_id:
        assert predicted == (concept_id,)
        assert [issue.code for issue in validate(changed) if issue.severity is Severity.ERROR] == [
            IssueCode.SELF_PREREQUISITE
        ]
    elif predicted is None:
        assert find_cycles(changed) == []
        learning_order(changed)
    else:
        # The predicted loop is real: each step is a link in the changed graph.
        links = {(concept.id, needed) for concept in changed for needed in concept.prerequisites}
        for current, following in zip(predicted, (*predicted[1:], predicted[0]), strict=True):
            assert (current, following) in links
        assert find_cycles(changed)
        with pytest.raises(GraphError):
            learning_order(changed)


@given(acyclic_graphs())
def test_closures_agree_with_each_other(graph: list[ConceptNode]) -> None:
    ids = [concept.id for concept in graph]
    direct = {concept.id: set(concept.prerequisites) for concept in graph}

    def naive(concept_id: str) -> set[str]:
        found: set[str] = set()
        frontier = list(direct[concept_id])
        while frontier:
            current = frontier.pop()
            if current not in found:
                found.add(current)
                frontier.extend(direct[current])
        return found

    for concept_id in ids:
        needed = everything_needed_by(graph, concept_id)
        assert needed == naive(concept_id)
        for other in ids:
            assert (other in needed) == (concept_id in everything_that_needs(graph, other))
