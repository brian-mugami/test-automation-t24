class T24TestError(AssertionError):
    def __init__(self, what_happened: str, why: str = "", how_to_fix: str = ""):
        self.what_happened = what_happened
        self.why = why
        self.how_to_fix = how_to_fix

        lines = [what_happened]
        if why:
            lines.append(f"Why: {why}")
        if how_to_fix:
            lines.append(f"Fix: {how_to_fix}")
        super().__init__("\n".join(lines))