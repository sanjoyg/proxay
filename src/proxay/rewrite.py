import re
from dataclasses import dataclass, field
from typing import List

@dataclass
class RewriteRule:
    find: re.Pattern
    replace: str

@dataclass
class RewriteRules:
    rules: List[RewriteRule] = field(default_factory=list)

    def append_rule(self, rule: RewriteRule) -> "RewriteRules":
        return RewriteRules(self.rules + [rule])

    def rewrite(self, value: str) -> str:
        rewritten = value
        for rule in self.rules:
            rewritten = rule.find.sub(rule.replace, rewritten)
        return rewritten
