"""
Filter through the food graph to find all the foods that we should use for ML,
then create mappings from Bing ID/Food 101 ID to the food name and search query

TODO see documentation of endpoint (DJ)
We expect

"""
import requests


def get_food_graph():
    """Get the MyFoodRepo food graph that contains the metadata (names etc.) associated with each food class

    Returns:
        food graph as JSON (key to use: 'nodes')
    """
    endpoint = "https://www.myfoodrepo.org/api/v1/food_case_foods/graph"
    resp = requests.get(endpoint)

    assert resp.status_code == 200
    graph = resp.json()['data']['food_graph']

    # print(graph)
    print(len(graph['nodes']), "nodes in food graph")
    return graph


def get_all_machine_learn_nodes():
    """Get all nodes marked with 'should_machine_learn' as a dict

    Returns:
        dict: mapping from each food class ID to its node in the food graph
    """
    map_class_id_to_node = dict()
    graph = get_food_graph()
    for node in graph['nodes']:
        if node.get('should_machine_learn', False):  # check that this field exists and is set to True
            class_id = node['id']
            map_class_id_to_node[class_id] = node

    return map_class_id_to_node


def get_classnames_bing_food101():
    """Get all nodes in the food graph, and print the node if it is considered
    a food in both the 2017 Bing Crawl and the Food101 dataset.

    TODO remove this, only needed for determining which classes to use in data collection!

    Returns:
        dict: mapping from each food class ID to its node in the food graph
    """
    graph = get_food_graph()

    map_class_id_to_node = dict()
    for node in graph['nodes']:

        class_id = node['id']
        map_class_id_to_node[class_id] = node

        if node.get('should_machine_learn', False):  # check that this field exists and is set to True
            key_bing = 'bing_crawl_2017'
            key_food_101 = 'food_101'

            if key_bing in node and key_food_101 in node:
                # Must occur in both datasets!
                print(node, "in bing crawl and food101")

    return map_class_id_to_node


if __name__ == "__main__":
    get_classnames_bing_food101()
