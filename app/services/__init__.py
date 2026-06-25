"""Business logic services for the triage pipeline.

Modules:
    - classifier:  Orchestrates rule evaluation and returns case_type + severity
    - router:      Maps a case_type to a responsible department
    - summarizer:  Builds the agent_summary string from message + classification
    - safety:      Post-generation filter that rewrites forbidden phrases
    - rules:       Individual rule detectors (one file per case_type)
"""
