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

    net_copy = copy.deepcopy(net)
    for node in net_copy["nodes"]:
        node_id = str(node["id"])
        if node_id in scenario:
            _set_cpt_weight(node["tbl"], node["id"], float(scenario[node_id]))

    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, prefix="harness_input_"
    )
    json.dump(net_copy, tmp)
    tmp.close()
    return tmp.name


def _set_cpt_weight(tbl: dict, node_id: int, weight: float) -> None:
    """Recursively set yes/no probability for node_id at every leaf of its CPT."""
    yes_key = str(node_id) + "yes"
    no_key  = str(node_id) + "no"
    if yes_key in tbl:
        tbl[yes_key] = round(weight, 4)
        tbl[no_key]  = round(1.0 - weight, 4)
    else:
        for v in tbl.values():
            if isinstance(v, dict):
                _set_cpt_weight(v, node_id, weight)
