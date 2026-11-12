"""
Attack Ladder input processor.

Takes a scenario dict {node_id_str: weight} and the adapter_config,
injects weights into the network JSON CPT structure, and returns the
path to a modified network file ready for headless_sampler.js.
"""

import copy
import json
import tempfile


def discover_inputs(adapter_config: dict) -> list[dict]:
    """
    Read the network template and return the input parameter schema:
    [{"id": "1", "description": "Node title", "type": "float",
      "range": [0.01, 0.99], "nominal": 0.5}, ...]
    """
    with open(adapter_config["network_template"]) as f:
        net = json.load(f)
    return [
        {
            "id": str(node["id"]),
            "description": node.get("title", f"Node {node['id']}"),
            "type": "float",
            "range": [0.01, 0.99],
            "nominal": 0.5,
        }
        for node in net["nodes"]
    ]


def process(scenario: dict, adapter_config: dict) -> str:
    """
    Inject LHS weights into the network CPT structure.

    scenario      : {node_id_str: weight}  e.g. {"1": 0.42, "7": 0.81}
    adapter_config: from harness_config tool.adapter_config

    Returns path to a temporary network JSON file (caller must delete it).
    """
    with open(adapter_config["network_template"]) as f:
        net = json.load(f)

    leak = float(adapter_config.get("leak", 0.0))
    net_copy = copy.deepcopy(net)
    for node in net_copy["nodes"]:
        node_id = str(node["id"])
        if node_id in scenario:
            _set_cpt_weight(node["tbl"], node["id"], float(scenario[node_id]), leak)

    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, prefix="harness_input_"
    )
    json.dump(net_copy, tmp)
    tmp.close()
    return tmp.name


def _set_cpt_weight(tbl: dict, node_id: int, weight: float,
                    leak: float = 0.0, _foothold: bool = False,
                    _depth: int = 0) -> None:
    """
    Foothold-gated CPT mapping.

    The CPT is a nest of parent-state keys ("<pid>yes" / "<pid>no") ending in
    a leaf {"<node>yes": p, "<node>no": 1-p}. For each leaf:
      - entry node (no parents, leaf at the top level) -> P(yes) = weight
      - at least one parent compromised on the path   -> P(yes) = weight
      - no parent compromised                          -> P(yes) = leak
    """
    yes_key = str(node_id) + "yes"
    no_key  = str(node_id) + "no"
    if yes_key in tbl:
        p = weight if (_depth == 0 or _foothold) else leak
        tbl[yes_key] = round(p, 4)
        tbl[no_key]  = round(1.0 - p, 4)
        return
    for key, v in tbl.items():
        if isinstance(v, dict):
            _set_cpt_weight(v, node_id, weight, leak,
                            _foothold or key.endswith("yes"), _depth + 1)


def describe_model(adapter_config: dict) -> dict:
    """
    Optional adapter hook: structural facts about the model for the AI preamble.
    Derived from the network itself, so the AI doesn't depend on the SME
    having typed node IDs into the free-text context.
    """
    with open(adapter_config["network_template"]) as f:
        net = json.load(f)
    parents = {str(n["id"]): [] for n in net["nodes"]}
    has_child = set()
    for e in net["edges"]:
        src, dst = str(e["source"]["id"]), str(e["target"]["id"])
        parents[dst].append(src)
        has_child.add(src)
    nodes = {
        str(n["id"]): {"title": n.get("title", f"Node {n['id']}"),
                       "parents": sorted(parents[str(n["id"])], key=int)}
        for n in net["nodes"]
    }
    leak = float(adapter_config.get("leak", 0.0))
    return {
        "summary": f"{len(nodes)} nodes, {len(net['edges'])} directed edges",
        "entry_nodes": sorted((k for k, v in parents.items() if not v), key=int),
        "exit_nodes":  sorted((k for k in nodes if k not in has_child), key=int),
        "input_semantics": (
            "Each input parameter is a node ID; its value w is the probability the "
            "attacker compromises that node given at least one parent node is "
            f"compromised (entry nodes: probability w outright). With no compromised "
            f"parent the probability is {leak}. Resilience = % of Monte Carlo runs in "
            "which no exit node is compromised."
        ),
        "nodes": nodes,
    }
