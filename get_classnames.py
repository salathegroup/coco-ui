"""
Filter through the food graph to find all the foods that we should use for ML,
then create mappings from Bing ID/Food 101 ID to the food name and search query

TODO see documentation of endpoint (DJ)
We expect

"""
import requests


def get_classnames_bing_food101():
    """TODO this should not be a single function, too many decisions"""
    endpoint = "https://www.myfoodrepo.org/api/v1/food_case_foods/graph"
    resp = requests.get(endpoint)

    assert resp.status_code == 200
    graph = resp.json()['data']['food_graph']

    print(graph)
    print(len(graph['nodes']), "nodes in food graph")

    #print(len([node for node in graph['nodes'] if 'food_101' in node]))

    # map_bing_id_to_name = dict()  # keep mapping from bing class ID to human readable food name
    # map_bing_id_to_search_terms = dict()  # keep mapping from bing class ID to search query
    # map_food_101_id_to_name = dict()  # keep mapping from food101 class ID to human readable food name
    # map_food_101_id_to_search_terms = dict()  # keep mapping from food101 class ID to search query
    # # TODO remove the other mappings, should use class ID only
    map_class_id_to_node = dict()
    # map_class_id_to_name = dict()  # keep mapping from database class ID to human readable food name
    # map_class_id_to_search_terms = dict()  # keep mapping from database class ID to search query

    for node in graph['nodes']:

        class_id = node['id']
        map_class_id_to_node[class_id] = node

        if node.get('should_machine_learn', False):  # check that this field exists and is set to True
            key_bing = 'bing_crawl_2017'
            key_food_101 = 'food_101'
            # display_name = node['display_name_translations']['en']  # TODO change to display_name/DJ column
            # search_query = node['search_terms']

            if key_bing in node and key_food_101 in node:
                # Must occur in both datasets!
                print(node, "in bing crawl and food101")

                # class_id = node['id']
                # map_class_id_to_node[class_id] = node
                # map_class_id_to_name[class_id] = display_name
                # map_class_id_to_search_terms[class_id] = search_query
                #
                # bing_id = node[key_bing]
                # food_101_id = node[key_food_101]

                # map_bing_id_to_name[bing_id] = display_name
                # map_bing_id_to_search_terms[bing_id] = search_query
                # map_food_101_id_to_name[food_101_id] = display_name
                # map_food_101_id_to_search_terms[food_101_id] = search_query

    print(len(map_class_id_to_node), "classes that occur in food101 AND bing")
    for class_id, node in map_class_id_to_node.items():
        print(class_id, node['display_name_translations']['en'])
    #
    # print("Longest names")
    # print("bing", max(map_bing_id_to_name.values(), key=lambda x: len(x)))
    # print("food101", max(map_food_101_id_to_name.values(), key=lambda x: len(x)))

    return map_class_id_to_node


if __name__ == "__main__":
    get_classnames_bing_food101()
