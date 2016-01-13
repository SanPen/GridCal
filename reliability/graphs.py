import networkx as nx


class GraphX(nx.Graph):
    """
    Graph implementation based on the NetworkX library
    """

    def find_all_paths(self, start, end, path=[]):
        """
        Finds all paths between the nodes start and end
        """
        path = path + [start]
        if start == end:
            return [path]
        if start not in self:
            return []
        paths = []
        for node in self[start]:
            if node not in path:
                new_paths = self.find_all_paths(node, end, path)
                for new_path in new_paths:
                    paths.append(new_path)
        return paths


class Graph(dict):
    """
    Own graph implementation based on standard dictionary
    """
    def __init__(self, *args, **kw):
        super(Graph,self).__init__(*args, **kw)
        self.itemlist = super(Graph,self).keys()

    def nodes(self):
        """ returns the vertices of a graph """
        return list(self.keys())

    def edges(self):
        """ returns the edges of a graph """
        return self.__generate_edges()

    def add_vertex(self, vertex):
        """
        """
        if vertex not in self:
            self[vertex] = set()

    def add_edge(self, v1, v2):
        """ assumes that edge is of type set, tuple or list;
            between two vertices can be multiple edges!
        """
        if v1 not in self:
            self[v1] = set()

        if v2 not in self:
            self[v2] = set()

        self[v1].add(v2)
        self[v2].add(v1)

    def __generate_edges(self):
        """ A static method generating the edges of the
            graph "graph". Edges are represented as sets
            with one (a loop back to the vertex) or two
            vertices
        """
        edges = []
        for vertex in self:
            for neighbour in self[vertex]:
                if {neighbour, vertex} not in edges:
                    edges.append({vertex, neighbour})
        return edges

    def __str__(self):
        res = "vertices: "
        for k in self:
            res += str(k) + " "
        res += "\nedges: "
        for edge in self.__generate_edges():
            res += str(edge) + " "
        return res

    def find_all_paths(self, start, end, path=[]):
        """
        Finds all paths between the nodes start and end
        """
        path = path + [start]
        if start == end:
            return [path]
        if start not in self:
            return []
        paths = []
        for node in self[start]:
            if node not in path:
                new_paths = self.find_all_paths(node, end, path)
                for new_path in new_paths:
                    paths.append(new_path)
        return paths


def find_all_paths_NR(graph, start, end):
        path  = []
        paths = []
        queue = [(start, end, path)]
        while queue:
            start, end, path = queue.pop()
            #print('PATH', path)

            path = path + [start]
            if start == end:
                paths.append(path)
            for node in set(graph[start]).difference(path):
                queue.append((node, end, path))
        return paths

def get_all_paths(graph, start_list, end_list):
    import progressbar
    progress = progressbar.ProgressBar()

    results = dict()

    for end in progress(end_list):
        paths = list()

        for start in start_list:

            paths.append(find_all_paths_NR(graph, start, end))

        results[end] = paths

    return results


if __name__ == "__main__":

    g = { "a" : set(["d", "b"]),
          "b" : set(["c"]),
          "c" : set(["b", "c", "d", "e"]),
          "d" : set(["a", "c"]),
          "e" : set(["c"]),
          "f" : set([])
        }


    graph = Graph(g)

    print("Vertices of graph:")
    print(graph.nodes())

    print("Edges of graph:")
    print(graph.edges())

    print("Add vertex:")
    graph.add_vertex("z")

    print("Vertices of graph:")
    print(graph.nodes())

    print("Add an edge:")
    graph.add_edge("a","z")

    print("Vertices of graph:")
    print(graph.nodes())

    print("Edges of graph:")
    print(graph.edges())

    print('Adding an edge {"x","y"} with new vertices:')
    graph.add_edge("x","y")
    print("Vertices of graph:")
    print(graph.nodes())
    print("Edges of graph:")
    print(graph.edges())

    paths = graph.find_all_paths('a', 'c')
    print("paths from a to c:")
    print(paths)


    gx = GraphX(g)
    paths = gx.find_all_paths('a', 'c')
    print("paths from a to c:")
    print(paths)