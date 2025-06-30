from one_dragon.base.matcher.match_result import MatchResult


class OcrMatchResult(MatchResult):

    def __init__(
            self,
            c: float,
            x: float | int,
            y: float | int,
            w: float | int,
            h: float | int,
            template_scale: float = 1,
            data: str | None = None
    ):
        MatchResult.__init__(
            self,
            c=c,
            x=x,
            y=y,
            w=w,
            h=h,
            template_scale=template_scale,
            data=data
        )
        self.data: str = data
