from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .blocks import PromptBlock
from .runtime import ActivePromptBundle


class TokenCounter(Protocol):
    def count(self, text: str) -> int: ...


class ConservativeCharTokenCounter:
    """Deterministic deployment-independent estimate. Real deployment may inject the frozen tokenizer counter."""
    def __init__(self, chars_per_token: float = 2.5) -> None:
        if chars_per_token <= 0: raise ValueError("chars_per_token must be positive")
        self.chars_per_token=chars_per_token
    def count(self,text:str)->int:
        return max(1,int((len(text)+self.chars_per_token-1)//self.chars_per_token))


@dataclass(frozen=True, slots=True)
class PromptBudgetReport:
    context_length: int
    reserved_output_tokens: int
    safety_tokens: int
    static_tokens: int
    dynamic_tokens: tuple[tuple[str,int],...]
    total_input_tokens: int
    available_input_tokens: int

    @property
    def fits(self) -> bool:
        return self.total_input_tokens <= self.available_input_tokens


class PromptBudgetExceeded(ValueError):
    def __init__(self, report: PromptBudgetReport) -> None:
        super().__init__(f"prompt budget exceeded: input={report.total_input_tokens} available={report.available_input_tokens}; no truncation performed")
        self.report=report


class PromptBudgetPlanner:
    """Measures; never truncates, drops blocks, reduces output budget or changes models."""
    def __init__(self,counter:TokenCounter|None=None,safety_tokens:int=1024) -> None:
        self.counter=counter or ConservativeCharTokenCounter(); self.safety_tokens=safety_tokens

    def check(self,bundle:ActivePromptBundle,blocks:tuple[PromptBlock,...],*,context_length:int)->PromptBudgetReport:
        static=self.counter.count(bundle.text)
        dynamic=tuple((b.kind.value,self.counter.count(b.content)) for b in blocks)
        available=context_length-bundle.max_output_tokens-self.safety_tokens
        report=PromptBudgetReport(context_length,bundle.max_output_tokens,self.safety_tokens,static,dynamic,static+sum(x[1] for x in dynamic),available)
        if available <= 0 or not report.fits: raise PromptBudgetExceeded(report)
        return report
