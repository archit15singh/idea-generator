"""idea_factory: typed DAG scaffolding for the idea-factory skill.

Code enforces contracts; agents do the reasoning.
"""

from idea_factory.schema import *  # noqa: F401,F403
from idea_factory.pm import (  # noqa: F401
    CANONICAL_MARKETS,
    build_builder_input,
    build_clusterer_input,
    build_scorer_input,
    build_validator_input,
    default_scout_input,
    get_runtime_started_at,
    html_to_summary,
    mark_clusterer_run,
    mark_runtime_started,
)