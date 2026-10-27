"""Environment-specific edge restrictions; original GeoJSON is never rewritten."""
import hashlib
import json

def apply_route_policy(graph, config):
    blocked = set()
    pairs = {(e.start, e.end) for e in graph.edges}
    for pair in config.get('blocked_connections', []):
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError('blocked_connections requires pairs of graph node IDs')
        a, b = pair
        if any(isinstance(n, bool) or not isinstance(n, (str, int)) for n in pair):
            raise ValueError('Invalid blocked node ID')
        if a == b or a not in graph.nodes or b not in graph.nodes:
            raise ValueError('Blocked connection references missing/equal nodes')
        if (a, b) not in pairs and (b, a) not in pairs:
            raise ValueError(f'Blocked connection does not exist: {a} <-> {b}')
        blocked.update(((a, b), (b, a)))
    if not blocked:
        return
    graph.edges = [e for e in graph.edges if (e.start, e.end) not in blocked]
    graph._adj = {n: [] for n in graph.nodes}
    for edge in graph.edges:
        graph._adj[edge.start].append(edge)
    graph.revision = hashlib.sha256((graph.revision + json.dumps(
        config['blocked_connections'], sort_keys=True)).encode()).hexdigest()
