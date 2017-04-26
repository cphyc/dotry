import unittest

from scyframework.ordering import Node, Graph


def test_node():
    node1, node2, node3, node4 = [Node(name=str(i+1))
                                  for i in range(4)]
    node1.link_parent(node2)
    node2.link_parent(node3)
    node3.link_parent(node4)
    node3.link_parent(node2)

    def check_eq(a, b):
        for el in a:
            assert el in b

    yield check_eq, node1.parents, [node2]
    yield check_eq, node2.parents, [node3]
    yield check_eq, node3.parents, [node4, node2]


def test_graph_orientation():
    """Check (top->down for direct links)
            2
           / \
          1   3
           \ /
            4
    """
    node1, node2, node3, node4 = nodes = [Node(name=str(i+1))
                                          for i in range(4)]
    node1.link_parent(node2)
    node3.link_parent(node2)
    node4.link_parent(node1)
    node4.link_parent(node3)

    g = Graph(nodes)

    ordering = g.find_ordering(node4)
    good_order1 = [node2, node3, node1, node4]
    good_order2 = [node2, node1, node3, node4]

    result = (all([ordering[i] == good_order1[i] for i in range(4)]) or
              all([ordering[i] == good_order2[i] for i in range(4)]))

    if not result:
        print(ordering)
        print(good_order1)
        print(good_order2)
    assert result
