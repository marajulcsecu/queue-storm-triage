"""Individual classification rules.

Each module exposes a single function that returns True/False for whether
the input message matches that rule. Rules are evaluated in priority order
by app.services.classifier, with phishing always evaluated first.
"""
