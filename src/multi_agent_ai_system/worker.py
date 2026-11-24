"""Isolated live CrewAI invocation; stdin and stdout use JSON."""
import contextlib
import json
import sys
from pathlib import Path


def hosted_definition():
    # Hosted assistants are text-only; no arbitrary URL fetches or external writes.
    definition = json.loads(Path(__file__).with_name("flow.json").read_text())
    definition["config"] = {"tracing": False, "max_method_calls": 12}
    for method in definition["methods"].values():
        action = method["do"]
        config = action.get("with", {})
        agents = config.get("agents", {}).values() if action["call"] == "crew" else [config]
        for agent in agents:
            agent.pop("tools", None)
            agent.pop("apps", None)
            if "goal" in agent:
                agent["goal"] += " Hosted mode is text-only: do not claim to access external sources or files, and state that limitation when relevant."
    return definition


def main():
    data = json.load(sys.stdin)
    with contextlib.redirect_stdout(sys.stderr):
        from crewai.flow import Flow
        definition = hosted_definition()
        flow = Flow.from_declaration(contents=definition)
        result = flow.kickoff(inputs={"message": data["message"], "user_id": data["user_id"]})
    answer = getattr(result, "raw", result)
    if not isinstance(answer, str) or not answer.strip():
        raise RuntimeError("CrewAI returned no text")
    print(json.dumps({"answer": answer}))


if __name__ == "__main__":
    main()
